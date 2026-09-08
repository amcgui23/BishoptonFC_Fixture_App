import re, math
from datetime import datetime
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

APP_CACHE_VERSION = "v1.0.7"

st.set_page_config(page_title="Bishopton FC Fixture & Form Guide", page_icon="⚽", layout="wide")

BASE = "https://www.pjdyfl.co.uk"
DIV_URLS = {i: f"{BASE}/2014-division-{i}" for i in range(1, 5)}
TABLE_URLS = [f"{BASE}/leaguestablefeed/1104", f"{BASE}/leaguetablefeed/1103"]
CUPS = {
    "Scottish Cup": f"{BASE}/scottish-cup-2014",
    "League Cup": f"{BASE}/league-cup-2014",
    "PJDYFL Cup": f"{BASE}/pjdyfl-cup-2014",
}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Safari/605.1.15",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Cache-Control": "no-cache",
}
COLS = ["date", "round", "home", "away", "hg", "ag", "status", "competition"]


def empty_df():
    return pd.DataFrame(columns=COLS)


def clean(x):
    text = re.sub(r"\s+", " ", str(x or "")).strip()
    text = re.sub(r"^(?:Round|Week|Matchday)\s*\d+\s*", "", text, flags=re.I)
    return text.strip()


def norm(x):
    return clean(x).lower()


def istarget(x):
    n = norm(x)
    return bool(re.search(r"\bbishopton\b.*\bblack\b", n))


def ordinal_date(s):
    s = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", clean(s))
    s = re.sub(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s*", "", s, flags=re.I)
    for f in ("%d %B %Y", "%d %b %Y", "%d %B", "%d %b"):
        try:
            dt = datetime.strptime(s, f)
            if dt.year == 1900:
                dt = dt.replace(year=2026)
            return dt.date()
        except ValueError:
            pass
    return None


@st.cache_data(ttl=300, show_spinner=False)
def fetch(url, _v=APP_CACHE_VERSION):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        return r.status_code, r.url, r.text
    except Exception:
        return 404, url, ""


def strip_venue(text):
    text = clean(text)
    venues = [
        "Holm Park", "Mossedge Community Pitch", "Nethercraigs Sport Complex",
        "Parklea playing fields", "India Tyres", "New Western Park", "Millburn Park",
        "Renfrew Leisure Centre", "Gray Street Astroturf", "TORYGLEN FOOTBALL CENTRE",
        "Williams Street Football Park", "Cowan Park", "Seedhill Playing Fields",
        "Clydebank Leisure Centre", "Gleniffer Thistle", "Paisley Grammar School"
    ]
    for v in sorted(venues, key=len, reverse=True):
        text = re.sub(r"\b" + re.escape(v) + r"\b", "", text, flags=re.I)
    return clean(text)


def parse_matches(url, competition):
    status, final_url, html = fetch(url)
    if status != 200 or not html:
        return empty_df(), {"url": final_url, "http": status, "parsed": 0}

    soup = BeautifulSoup(html, "html.parser")
    out = []

    current_date = None
    current_round = "League/Cup"

    for element in soup.find_all(['div', 'tr', 'li', 'p']):
        text = clean(element.get_text(" ", strip=True))
        
        date_match = re.search(r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)?,?\s*\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*(?:\s+\d{4})?", text, re.I)
        if date_match and len(text) < 60:
            parsed_dt = ordinal_date(date_match.group(0))
            if parsed_dt:
                current_date = parsed_dt
            rnd_match = re.search(r"Round:\s*([^\s]+)", text, re.I)
            if rnd_match:
                current_round = rnd_match.group(1)
            continue

        if not current_date:
            continue

        # Finished Match
        m = re.search(r"^(?P<home>.+?)\s+(?P<hg>\d+)\s*[-–]\s*(?P<ag>\d+)\s+(?P<away>.+?)$", text)
        if not m:
            m = re.search(r"^(?P<home>[A-Za-z\s()0-9.-]+?)\s+(?P<hg>\d+)\s+(?P<ag>\d+)\s+(?P<away>[A-Za-z\s()0-9.-]+?)$", text)
        if m:
            h, a = strip_venue(m.group("home")), strip_venue(m.group("away"))
            if h and a and h != a and len(h) < 60 and len(a) < 60:
                out.append(dict(date=current_date, round=current_round, home=h, away=a,
                                hg=int(m.group("hg")), ag=int(m.group("ag")), status="FT", competition=competition))
                continue

        # Scheduled Match
        m = re.search(r"^(?P<home>.+?)\s+(?P<kick>\d{1,2}:\d{2})\s+(?P<away>.+)$", text)
        if m:
            h, a = strip_venue(m.group("home")), strip_venue(m.group("away"))
            if h and a and h != a and len(h) < 60 and len(a) < 60:
                out.append(dict(date=current_date, round=current_round, home=h, away=a,
                                hg=None, ag=None, status=m.group("kick"), competition=competition))
                continue

        # Postponed Match
        m = re.search(r"^(?P<home>.+?)\s+P-P\s+(?P<away>.+)$", text, re.I)
        if m:
            h, a = strip_venue(m.group("home")), strip_venue(m.group("away"))
            if h and a and h != a and len(h) < 60 and len(a) < 60:
                out.append(dict(date=current_date, round=current_round, home=h, away=a,
                                hg=None, ag=None, status="Postponed", competition=competition))

    info = {"url": final_url, "http": status, "parsed": len(out)}
    if not out:
        return empty_df(), info
    df = pd.DataFrame(out, columns=COLS).drop_duplicates(["date", "home", "away", "competition"])
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True), info


@st.cache_data(ttl=300, show_spinner=False)
def load_data(_v=APP_CACHE_VERSION):
    div, cups, diagnostics = {}, {}, []
    for d, u in DIV_URLS.items():
        try:
            df, info = parse_matches(u, f"Division {d}")
            div[d] = df
            diagnostics.append(f"Division {d}: {info}")
        except Exception as e:
            div[d] = empty_df()
            diagnostics.append(f"Division {d}: ERROR {type(e).__name__}: {e}")
    for n, u in CUPS.items():
        try:
            df, info = parse_matches(u, n)
            cups[n] = df
            diagnostics.append(f"{n}: {info}")
        except Exception as e:
            cups[n] = empty_df()
            diagnostics.append(f"{n}: ERROR {type(e).__name__}: {e}")
    return div, cups, diagnostics


def results(df, team):
    cols = ["date", "opponent", "GF", "GA", "GD", "Result", "venue", "competition"]
    if df.empty:
        return pd.DataFrame(columns=cols)
    rows = []
    for _, r in df.iterrows():
        if r.status != "FT":
            continue
        if istarget(r.home) if istarget(team) else norm(r.home) == norm(team):
            gf, ga, opp, venue = int(r.hg), int(r.ag), r.away, "H"
        elif istarget(r.away) if istarget(team) else norm(r.away) == norm(team):
            gf, ga, opp, venue = int(r.ag), int(r.hg), r.home, "A"
        else:
            continue
        rows.append({"date": r.date, "opponent": opp, "GF": gf, "GA": ga, "GD": gf-ga,
                     "Result": "W" if gf > ga else "D" if gf == ga else "L", "venue": venue,
                     "competition": r.competition})
    return pd.DataFrame(rows, columns=cols).sort_values("date", ascending=False) if rows else pd.DataFrame(columns=cols)


def form(df, team, n=5):
    return results(df, team).head(n)


def strength(r):
    if r.empty:
        return None
    def ppg(x):
        return (3*(x.Result == "W").sum() + (x.Result == "D").sum()) / len(x)
    recent = r.head(5)
    return .55*ppg(r) + .30*ppg(recent) + .15*(1 + math.tanh(recent.GD.mean()/3))


def win_chance(a, b, home=True):
    sa, sb = strength(a), strength(b)
    if sa is None or sb is None:
        return None
    x = sa - sb + (0.18 if home else -0.02)
    return max(.05, min(.95, 1/(1+math.exp(-1.35*x))))


def calculated_table(df):
    cols = ["Team", "P", "W", "D", "L", "GF", "GA", "GD", "Pts"]
    if df.empty or not {"home", "away"}.issubset(df.columns):
        return pd.DataFrame(columns=cols)
    teams = set(df.home.dropna()) | set(df.away.dropna())
    rows = []
    for t in teams:
        r = results(df, t)
        if r.empty:
            rows.append([t, 0, 0, 0, 0, 0, 0, 0, 0])
            continue
        w = (r["Result"] == "W").sum()
        d = (r["Result"] == "D").sum()
        l = (r["Result"] == "L").sum()
        gf = r["GF"].sum()
        ga = r["GA"].sum()
        gd = gf - ga
        pts = 3 * w + d
        rows.append([t, len(r), w, d, l, gf, ga, gd, pts])
    df_out = pd.DataFrame(rows, columns=cols).sort_values(["Pts", "GD", "GF"], ascending=False).reset_index(drop=True)
    df_out["Team"] = df_out["Team"].apply(clean)
    return df_out


@st.cache_data(ttl=300, show_spinner=False)
def official_table(_v=APP_CACHE_VERSION):
    for url in TABLE_URLS:
        try:
            html = fetch(url)[2]
            tabs = pd.read_html(html)
            for t in tabs:
                cols = [str(c).strip().lower() for c in t.columns]
                joined = " ".join(cols)
                if len(t) >= 5 and ("club" in joined or "team" in joined) and "pts" in joined:
                    team_col = [c for c in t.columns if "club" in str(c).lower() or "team" in str(c).lower()][0]
                    t[team_col] = t[team_col].apply(clean)
                    return t, url
        except Exception:
            continue
    return None, None


def format_form_df(df_in, display_cols):
    if df_in.empty:
        return pd.DataFrame(columns=display_cols)
    df_out = df_in[display_cols].copy()
    if "date" in df_out.columns:
        df_out["date"] = pd.to_datetime(df_out["date"], errors="coerce").dt.strftime("%d/%m")
    return df_out


div, cups, diagnostics = load_data()
league = div.get(4, empty_df())
all_nonempty = [x for x in div.values() if not x.empty]
all_div = pd.concat(all_nonempty, ignore_index=True) if all_nonempty else empty_df()

st.title("⚽ Bishopton FC Black 2014")

with st.sidebar:
    st.header("Data Controls")
    if st.button("🔄 Force Clear & Refresh"):
        st.cache_data.clear()
        st.rerun()
    with st.expander("Diagnostics"):
        st.caption(f"App Cache Version: {APP_CACHE_VERSION}")
        for item in diagnostics:
            st.write(item)

col_fx, col_tbl = st.columns([1, 1])

with col_fx:
    st.subheader("Division 4 Fixtures")
    if league.empty:
        st.info("No Division 4 fixtures currently loaded.")
    else:
        fx = league[league.home.map(istarget) | league.away.map(istarget)].sort_values("date")
        upcoming = fx[fx.status != "FT"]
        completed = fx[fx.status == "FT"]

        st.markdown("#### 📅 Upcoming Matches")
        if upcoming.empty:
            st.caption("No upcoming league fixtures scheduled.")
        else:
            for _, r in upcoming.iterrows():
                opp = r.away if istarget(r.home) else r.home
                venue = "Home" if istarget(r.home) else "Away"
                br, orr = form(league, "Bishopton FC Black"), form(league, opp)
                p = win_chance(br, orr, istarget(r.home))
                with st.container(border=True):
                    st.markdown(f"**{r.date.strftime('%a %d %b %Y')}** • *{venue}*")
                    st.markdown(f"**Bishopton FC Black** vs **{opp}**")
                    st.caption(f"Kick-off / Status: **{r.status}**")
                    if p is not None:
                        st.caption(f"Estimated Win Chance: **{p:.0%}**")
                    
                    with st.expander("Form Guide"):
                        ca, cb = st.columns(2)
                        with ca:
                            st.write("**Bishopton FC**")
                            st.dataframe(format_form_df(br, ["date", "opponent", "GF", "GA", "Result"]), hide_index=True, use_container_width=True)
                        with cb:
                            st.write(f"**{opp}**")
                            st.dataframe(format_form_df(orr, ["date", "opponent", "GF", "GA", "Result"]), hide_index=True, use_container_width=True)

        st.markdown("#### 🏁 Recent Results")
        if completed.empty:
            st.caption("No completed results recorded yet.")
        else:
            for _, r in completed.iterrows():
                opp = r.away if istarget(r.home) else r.home
                score = f"{int(r.hg)} - {int(r.ag)}"
                with st.container(border=True):
                    st.markdown(f"**{r.date.strftime('%a %d %b %Y')}**")
                    st.markdown(f"**Bishopton FC Black** `{score}` **{opp}**")

with col_tbl:
    st.subheader("Division 4 Standings")
    ot, ot_url = official_table()
    tbl_data = ot if ot is not None else calculated_table(league)
    
    st.dataframe(
        tbl_data,
        hide_index=True,
        use_container_width=True,
        height=600
    )
    if ot is not None:
        st.caption(f"Official PJDYFL table source: {ot_url}")
    else:
        st.caption("Calculated dynamic standings from parsed Division 4 results.")

st.divider()
st.header("🏆 Cup Competitions")

cup_found = False
for cup_name, cdf in cups.items():
    if cdf.empty:
        continue
    cfx = cdf[cdf.home.map(istarget) | cdf.away.map(istarget)]
    if not cfx.empty:
        cup_found = True
        st.subheader(cup_name)
        for _, r in cfx.iterrows():
            opp = r["away"] if istarget(r["home"]) else r["home"]
            venue = "Home" if istarget(r["home"]) else "Away"
            round_label = str(r["round"]) if "round" in r else "Cup Round"
            status_str = f"{int(r['hg'])} - {int(r['ag'])}" if r["status"] == "FT" else str(r["status"])
            br, orr = form(all_div, "Bishopton FC Black"), form(all_div, opp)
            p = win_chance(br, orr, istarget(r["home"]))
            
            with st.container(border=True):
                st.markdown(f"**{r['date'].strftime('%a %d %b %Y')}** ({round_label}) • *{venue}*")
                st.markdown(f"**Bishopton FC Black** vs **{opp}** — `{status_str}`")
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Bishopton form", "".join(br.Result.tolist()) if not br.empty else "—")
                c2.metric("Opponent form", "".join(orr.Result.tolist()) if not orr.empty else "—")
                c3.metric("Est. Win Chance", f"{p:.0%}" if p is not None else "N/A")

                with st.expander("Opponent Form Guide"):
                    if orr.empty:
                        st.write("No recorded games for this opponent.")
                    else:
                        st.dataframe(format_form_df(orr, ["date", "opponent", "GF", "GA", "Result", "competition"]), hide_index=True, use_container_width=True)

if not cup_found:
    st.info("No Cup fixtures detected for Bishopton FC Black.")
