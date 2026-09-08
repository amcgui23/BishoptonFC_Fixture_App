import re, math
from datetime import datetime
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

st.set_page_config(page_title="Bishopton FC Fixture & Form Guide", page_icon="⚽", layout="wide")

BASE = "https://www.pjdyfl.co.uk"
TARGET = "Bishopton FC Black (2014)"
DIV_URLS = {i: f"{BASE}/2014-division-{i}" for i in range(1, 5)}
CUPS = {
    "Scottish Cup": f"{BASE}/scottish-cup-2014",
    "League Cup": f"{BASE}/league-cup-2014",
}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Safari/605.1.15",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
COLS = ["date", "round", "home", "away", "hg", "ag", "status", "competition"]


def empty_df():
    return pd.DataFrame(columns=COLS)


def clean(x):
    return re.sub(r"\s+", " ", str(x or "")).strip()


def norm(x):
    return clean(x).lower()


def istarget(x):
    return norm(x).startswith("bishopton fc black")


def ordinal_date(s):
    s = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", clean(s))
    for f in ("%A, %d %B %Y", "%d %B %Y"):
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            pass
    return None


@st.cache_data(ttl=900, show_spinner=False)
def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.status_code, r.url, r.text


def parse_line(line, date, rnd, competition):
    line = clean(line)
    if not date or not line:
        return None

    patterns = [
        r"^(.*?\))\s*(\d+)\s+(\d+)\s+(.*?)(?:\s+Half time score:|\s+Kick off time:|$)",
        r"^(.*?)\s+(\d+)\s+(\d+)\s+(.*?)(?:\s+Half time score:|\s+Kick off time:|$)",
    ]
    for p in patterns:
        m = re.match(p, line, re.I)
        if m:
            home, hg, ag, away = clean(m.group(1)), int(m.group(2)), int(m.group(3)), clean(m.group(4))
            if home and away and len(home) < 120 and len(away) < 120:
                return dict(date=date, round=rnd, home=home, away=away, hg=hg, ag=ag,
                            status="FT", competition=competition)

    patterns = [
        r"^(.*?\))\s*(\d{1,2}:\d{2})\s+(.*?)(?:\s+(?:[A-Z][A-Za-z .&'-]+(?:Community|Park|Centre|Complex|Astroturf|School|Ground|Fields?).*))?$",
        r"^(.*?)\s+(\d{1,2}:\d{2})\s+(.*)$",
    ]
    for p in patterns:
        m = re.match(p, line, re.I)
        if m:
            home, kick, away = clean(m.group(1)), m.group(2), clean(m.group(3))
            away = re.split(r"\s+(?:Mossedge Community Pitch|Holm Park|India Tyres|Nethercraigs Sport Complex|New Western Park|Millburn Park|Parklea playing fields|Seedhill Playing Fields|Gray Street Astroturf|TORYGLEN FOOTBALL CENTRE|Renfrew Leisure Centre|Williams Street Football Park|Cowan Park.*)$", away, flags=re.I)[0].strip()
            if home and away and len(home) < 120 and len(away) < 120:
                return dict(date=date, round=rnd, home=home, away=away, hg=None, ag=None,
                            status=kick, competition=competition)

    m = re.match(r"^(.*?)\s+P-P\s+(.*?)(?:\s+Kick off time:.*)?$", line, re.I)
    if m:
        return dict(date=date, round=rnd, home=clean(m.group(1)), away=clean(m.group(2)),
                    hg=None, ag=None, status="Postponed", competition=competition)

    return None


def strip_venue(text, leading=True):
    text = clean(text)
    venues = [
        "Holm Park", "Mossedge Community Pitch", "Nethercraigs Sport Complex",
        "Parklea playing fields", "India Tyres", "New Western Park", "Millburn Park",
        "Renfrew Leisure Centre", "Gray Street Astroturf", "TORYGLEN FOOTBALL CENTRE",
        "Williams Street Football Park", "Cowan Park", "Seedhill Playing Fields",
        "Clydebank Leisure Centre", "Gleniffer Thistle", "Paisley Grammar School"
    ]
    if leading:
        for v in sorted(venues, key=len, reverse=True):
            if re.match(r"^" + re.escape(v) + r"\b", text, re.I):
                return clean(text[len(v):])
    else:
        for v in sorted(venues, key=len, reverse=True):
            text = re.sub(r"\s*" + re.escape(v) + r"\s*$", "", text, flags=re.I)
    if leading:
        text = re.sub(r"^(?:[A-Z][A-Za-z'&.-]*(?:\s+[A-Z][A-Za-z'&.-]*){0,5})\s+(?:Park|Pitch|Fields?|Complex|Centre|Center|Astroturf|School)\b", "", text, flags=re.I).strip()
    else:
        text = re.sub(r"\s+(?:[A-Z][A-Za-z'&.-]*(?:\s+[A-Z][A-Za-z'&.-]*){0,5})\s+(?:Park|Pitch|Fields?|Complex|Centre|Center|Astroturf|School)\s*$", "", text, flags=re.I).strip()
    return clean(text)


def parse_match_segment(seg, date, rnd, competition):
    seg = clean(seg)
    if not seg or not date:
        return None

    m = re.search(r"(?P<home>.+?)(?P<hg>\d+)\s+(?P<ag>\d+)\s+(?P<away>.+?)\s+Half time score:\s*\d+\s*-\s*\d+", seg, re.I)
    if m:
        home = strip_venue(m.group("home"), leading=True)
        away = strip_venue(m.group("away"), leading=False)
        if home and away and len(home) < 120 and len(away) < 120:
            return dict(date=date, round=rnd, home=home, away=away,
                        hg=int(m.group("hg")), ag=int(m.group("ag")), status="FT",
                        competition=competition)

    m = re.search(r"(?P<home>.+?)\s+P-P\s+(?P<away>.+)$", seg, re.I)
    if m:
        home = strip_venue(m.group("home"), leading=True)
        away = strip_venue(m.group("away"), leading=False)
        if home and away and len(home) < 120 and len(away) < 120:
            return dict(date=date, round=rnd, home=home, away=away,
                        hg=None, ag=None, status="Postponed", competition=competition)

    m = re.search(r"(?P<home>.+?)(?P<kick>\d{1,2}:\d{2})\s+(?P<away>.+)$", seg)
    if m:
        home = strip_venue(m.group("home"), leading=True)
        away = strip_venue(m.group("away"), leading=False)
        if home and away and len(home) < 120 and len(away) < 120:
            return dict(date=date, round=rnd, home=home, away=away,
                        hg=None, ag=None, status=m.group("kick"), competition=competition)
    return None


def parse_matches(url, competition):
    status, final_url, html = fetch(url)
    soup = BeautifulSoup(html, "html.parser")

    text = clean(soup.get_text(" ", strip=True))
    date_re = re.compile(r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+\d{1,2}(?:st|nd|rd|th)\s+\w+\s+\d{4}", re.I)
    dates = list(date_re.finditer(text))
    out = []

    for i, dm in enumerate(dates):
        date = ordinal_date(dm.group(0))
        block_end = dates[i + 1].start() if i + 1 < len(dates) else len(text)
        block = text[dm.end():block_end]
        rm = re.search(r"Round:\s*([^\s]+)", block, re.I)
        rnd = rm.group(1) if rm else ""
        if rm:
            block = block[rm.end():]

        parts = re.split(r"Kick off time:\s*\d{1,2}:\d{2}", block, flags=re.I)
        for seg in parts[:-1]:
            parsed = parse_match_segment(seg, date, rnd, competition)
            if parsed:
                out.append(parsed)

    info = {
        "url": final_url,
        "http": status,
        "text_len": len(html),
        "raw_nodes": len(list(soup.stripped_strings)),
        "date_blocks": len(dates),
        "parsed": len(out),
    }
    if not out:
        return empty_df(), info
    df = pd.DataFrame(out, columns=COLS).drop_duplicates(["date", "home", "away", "competition", "round"])
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True), info


@st.cache_data(ttl=900, show_spinner=False)
def load_data():
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
    target = norm(team)
    for _, r in df.iterrows():
        if r.status != "FT":
            continue
        if norm(r.home) == target:
            gf, ga, opp, venue = int(r.hg), int(r.ag), r.away, "H"
        elif norm(r.away) == target:
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
    return pd.DataFrame(rows, columns=cols).sort_values(["Pts", "GD", "GF"], ascending=False).reset_index(drop=True)


@st.cache_data(ttl=900, show_spinner=False)
def official_table(div_num=4):
    url = DIV_URLS.get(div_num)
    if not url:
        return None, None
    try:
        status, final_url, html = fetch(url)
        tables = pd.read_html(html)
        for t in tables:
            cols = [str(c).strip().lower() for c in t.columns]
            joined = " ".join(cols)
            if len(t) >= 3 and any(k in joined for k in ["team", "club", "pos", "#"]) and "pts" in joined:
                return t, final_url
    except Exception:
        pass
    return None, None


div, cups, diagnostics = load_data()
league = div.get(4, empty_df())
all_nonempty = [x for x in div.values() if not x.empty]
all_div = pd.concat(all_nonempty, ignore_index=True) if all_nonempty else empty_df()

st.title("⚽ Bishopton FC Black 2014 — Fixtures & Form Guide")
st.caption("Live PJDYFL data • estimates are statistical guides, not betting odds")

with st.sidebar:
    st.header("Data")
    if st.button("🔄 Refresh PJDYFL data"):
        st.cache_data.clear(); st.rerun()
    st.write("Sources: PJDYFL 2014 Divisions 1–4, Scottish Cup and League Cup.")
    with st.expander("Data-source diagnostics"):
        for item in diagnostics:
            st.write(item)

st.header("🏆 Division 4")

# Layout Split: Fixtures on the left, League Table on the right
col_fx, col_tbl = st.columns([1, 1])

with col_fx:
    st.subheader("Bishopton FC Black Fixtures")
    if league.empty:
        st.error("Could not parse Division 4 fixtures from PJDYFL.")
    else:
        fx = league[league.home.map(istarget) | league.away.map(istarget)].sort_values("date")
        
        # Display Upcoming / Scheduled Fixtures First
        upcoming_fx = fx[fx.status != "FT"]
        completed_fx = fx[fx.status == "FT"]
        
        if not upcoming_fx.empty:
            st.markdown("#### 📅 Upcoming Fixtures")
            for _, r in upcoming_fx.iterrows():
                opp = r.away if istarget(r.home) else r.home
                home = istarget(r.home)
                st.markdown(f"**{r.date.strftime('%a %d %b %Y')}** — {'Home' if home else 'Away'}")
                st.markdown(f"**Bishopton FC Black** vs **{opp}** ({r.status})")
                br, orr = form(league, TARGET), form(league, opp)
                p = win_chance(br, orr, home)
                st.caption(f"Estimated Win Chance: **{p:.0%}**" if p is not None else "Estimated Win Chance: N/A")
                st.divider()

        st.markdown("#### 🏁 Completed Results")
        if completed_fx.empty:
            st.info("No completed results yet.")
        else:
            for _, r in completed_fx.iterrows():
                opp = r.away if istarget(r.home) else r.home
                home = istarget(r.home)
                score = f"{int(r.hg)}–{int(r.ag)}"
                st.markdown(f"**{r.date.strftime('%a %d %b %Y')}** — {'Home' if home else 'Away'}")
                st.markdown(f"**Bishopton FC Black** {score} **{opp}**")
                st.divider()

with col_tbl:
    st.subheader("Division 4 League Table")
    ot, ot_url = official_table(4)
    tbl_data = ot if ot is not None else calculated_table(league)
    
    # Render with full height so scrolling is not required
    st.dataframe(tbl_data, hide_index=True, use_container_width=True, height=600)
    
    if ot is not None:
        st.caption(f"Official PJDYFL table source: {ot_url}")
    else:
        st.caption("Fallback table calculated dynamically from parsed Division 4 match scores.")

st.header("🥇 Cup Competitions")
for cup, cdf in cups.items():
    st.subheader(cup)
    if cdf.empty:
        st.warning("Could not parse this competition from PJDYFL.")
        continue
    fx = cdf[cdf.home.map(istarget) | cdf.away.map(istarget)].sort_values("date")
    if fx.empty:
        st.info("No Bishopton FC Black fixture currently found.")
        continue
    for _, r in fx.iterrows():
        opp = r.away if istarget(r.home) else r.home
        home = istarget(r.home)
        score = f"{int(r.hg)}–{int(r.ag)}" if r.status == "FT" else r.status
        st.markdown(f"### {r.date.strftime('%a %d %b %Y')} — {'Home' if home else 'Away'}")
        st.markdown(f"**Bishopton FC Black** vs **{opp}** — **{score}**")
        br, orr = form(all_div, TARGET), form(all_div, opp)
        p = win_chance(br, orr, home)
        c1, c2, c3 = st.columns(3)
        c1.metric("Bishopton last 5", "".join(br.Result.tolist()) if not br.empty else "—")
        c2.metric("Opponent last 5", "".join(orr.Result.tolist()) if not orr.empty else "—")
        c3.metric("Estimated Bishopton win chance", f"{p:.0%}" if p is not None else "N/A")
        with st.expander("Opponent form guide"):
            if orr.empty:
                st.warning("No completed results found for this opponent in PJDYFL Divisions 1–4.")
            else:
                st.dataframe(orr[["date", "opponent", "GF", "GA", "Result", "competition"]].assign(date=lambda x: x.date.dt.strftime("%d/%m/%Y")), hide_index=True, use_container_width=True)
        st.divider()

st.caption("PJDYFL is the data source. This app is intended as a coaching/fan analytics tool and makes no guarantee about match outcomes.")
