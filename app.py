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
TABLE_URLS = [f"{BASE}/leaguestablefeed/1104", f"{BASE}/leaguetablefeed/1103"]
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

    # Completed result: the site currently renders e.g.
    # "Bishopton FC Black (2014)3 2 Bridge of weir United (2014)"
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

    # Future fixture: e.g. "Erskine Youth FC (2014)09:00 Bishopton FC Black (2014)"
    patterns = [
        r"^(.*?\))\s*(\d{1,2}:\d{2})\s+(.*?)(?:\s+(?:[A-Z][A-Za-z .&'-]+(?:Community|Park|Centre|Complex|Astroturf|School|Ground|Fields?).*))?$",
        r"^(.*?)\s+(\d{1,2}:\d{2})\s+(.*)$",
    ]
    for p in patterns:
        m = re.match(p, line, re.I)
        if m:
            home, kick, away = clean(m.group(1)), m.group(2), clean(m.group(3))
            # Remove common venue suffixes where they have been swallowed into away.
            away = re.split(r"\s+(?:Mossedge Community Pitch|Holm Park|India Tyres|Nethercraigs Sport Complex|New Western Park|Millburn Park|Parklea playing fields|Seedhill Playing Fields|Gray Street Astroturf|TORYGLEN FOOTBALL CENTRE|Renfrew Leisure Centre|Williams Street Football Park|Cowan Park.*)$", away, flags=re.I)[0].strip()
            if home and away and len(home) < 120 and len(away) < 120:
                return dict(date=date, round=rnd, home=home, away=away, hg=None, ag=None,
                            status=kick, competition=competition)

    # Postponed fixtures.
    m = re.match(r"^(.*?)\s+P-P\s+(.*?)(?:\s+Kick off time:.*)?$", line, re.I)
    if m:
        return dict(date=date, round=rnd, home=clean(m.group(1)), away=clean(m.group(2)),
                    hg=None, ag=None, status="Postponed", competition=competition)

    return None


def parse_matches(url, competition):
    status, final_url, html = fetch(url)
    soup = BeautifulSoup(html, "html.parser")

    # stripped_strings is more reliable than get_text("\\n") on TeamExpert pages,
    # because COMET match rows are made from nested HTML elements.
    raw = [clean(x) for x in soup.stripped_strings if clean(x)]

    date_re = re.compile(r"^(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+\d{1,2}(?:st|nd|rd|th)\s+\w+\s+\d{4}$", re.I)
    round_re = re.compile(r"^Round:\s*(.*)$", re.I)
    out = []
    date = None
    rnd = ""

    for line in raw:
        if date_re.match(line):
            date = ordinal_date(line)
            rnd = ""
            continue
        m = round_re.match(line)
        if m:
            rnd = m.group(1)
            continue
        if not date:
            continue
        parsed = parse_line(line, date, rnd, competition)
        if parsed:
            out.append(parsed)

    # Second strategy: the browser-readable text representation often joins
    # adjacent text nodes. Split it around date headings and parse each token.
    if not out:
        text = soup.get_text("\n", strip=True)
        lines = [clean(x) for x in text.splitlines() if clean(x)]
        date = None
        rnd = ""
        for line in lines:
            if date_re.match(line):
                date = ordinal_date(line); rnd = ""; continue
            m = round_re.match(line)
            if m: rnd = m.group(1); continue
            parsed = parse_line(line, date, rnd, competition)
            if parsed: out.append(parsed)

    if not out:
        return empty_df(), {"url": final_url, "http": status, "text_len": len(html), "raw_nodes": len(raw), "parsed": 0}

    df = pd.DataFrame(out, columns=COLS).drop_duplicates(["date", "home", "away", "competition", "round"])
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True), {"url": final_url, "http": status, "text_len": len(html), "raw_nodes": len(raw), "parsed": len(df)}


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
    if df.empty:
        return pd.DataFrame()
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
    return pd.DataFrame(rows).sort_values("date", ascending=False) if rows else pd.DataFrame()


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
    if df.empty or not {"home", "away"}.issubset(df.columns):
        return pd.DataFrame(columns=["Team", "P", "W", "D", "L", "GF", "GA", "GD", "Pts"])
    teams = set(df.home.dropna()) | set(df.away.dropna())
    rows = []
    for t in teams:
        r = results(df, t)
        w, d, l = (r.Result == "W").sum(), (r.Result == "D").sum(), (r.Result == "L").sum()
        rows.append([t, len(r), w, d, l, r.GF.sum(), r.GA.sum(), r.GD.sum(), 3*w+d])
    return pd.DataFrame(rows, columns=["Team", "P", "W", "D", "L", "GF", "GA", "GD", "Pts"]).sort_values(["Pts", "GD", "GF"], ascending=False).reset_index(drop=True)


@st.cache_data(ttl=900, show_spinner=False)
def official_table():
    for url in TABLE_URLS:
        try:
            html = fetch(url)[2]
            tabs = pd.read_html(html)
            for t in tabs:
                cols = [str(c).strip().lower() for c in t.columns]
                joined = " ".join(cols)
                if len(t) >= 5 and ("club" in joined or "team" in joined) and "pts" in joined:
                    return t, url
        except Exception:
            continue
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
st.subheader("Bishopton FC Black fixtures")
if league.empty:
    st.error("Could not parse Division 4 fixtures from PJDYFL. Open Data-source diagnostics in the sidebar for details.")
else:
    fx = league[league.home.map(istarget) | league.away.map(istarget)].sort_values("date")
    for _, r in fx.iterrows():
        opp = r.away if istarget(r.home) else r.home
        home = istarget(r.home)
        score = f"{int(r.hg)}–{int(r.ag)}" if r.status == "FT" else r.status
        st.markdown(f"### {r.date.strftime('%a %d %b %Y')} — {'Home' if home else 'Away'}")
        st.markdown(f"**Bishopton FC Black** vs **{opp}** — **{score}**")
        br, orr = form(league, TARGET), form(league, opp)
        p = win_chance(br, orr, home)
        c1, c2, c3 = st.columns(3)
        c1.metric("Bishopton last 5", "".join(br.Result.tolist()) if not br.empty else "—")
        c2.metric("Opponent last 5", "".join(orr.Result.tolist()) if not orr.empty else "—")
        c3.metric("Estimated Bishopton win chance", f"{p:.0%}" if p is not None else "N/A")
        with st.expander("Form guide"):
            a, b = st.columns(2)
            with a:
                st.write("**Bishopton FC Black**")
                st.dataframe(br[["date", "opponent", "GF", "GA", "Result"]].assign(date=lambda x: x.date.dt.strftime("%d/%m/%Y")), hide_index=True, use_container_width=True)
            with b:
                st.write(f"**{opp}**")
                st.dataframe(orr[["date", "opponent", "GF", "GA", "Result"]].assign(date=lambda x: x.date.dt.strftime("%d/%m/%Y")), hide_index=True, use_container_width=True)
        st.divider()

st.subheader("Division 4 League Table")
ot, ot_url = official_table()
if ot is not None:
    st.dataframe(ot, hide_index=True, use_container_width=True)
    st.caption(f"Official PJDYFL league table source: {ot_url}")
else:
    st.dataframe(calculated_table(league), hide_index=True, use_container_width=True)
    st.caption("Fallback table calculated from published Division 4 results because the table feed was not machine-readable.")

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
