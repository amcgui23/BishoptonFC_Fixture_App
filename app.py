import re, math
from datetime import datetime
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

APP_CACHE_VERSION = "v2.0.0"

FILE_ID = "1shpFhmc52QBr1z4eZV0g1g8KIuakU4rv"
CLUB_LOGO_URL = f"https://drive.google.com/thumbnail?id={FILE_ID}&sz=w1000"

st.set_page_config(
    page_title="Bishopton FC | Performance Hub",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@500;700;800;900&family=Inter:wght@400;500;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, sans-serif;
    }

    h1, h2, h3, h4, .hero-title {
        font-family: 'Montserrat', sans-serif !important;
        letter-spacing: -0.03em;
    }

    .main .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2.5rem !important;
        max-width: 1240px;
    }

    .hero-header {
        background: linear-gradient(135deg, #09131e 0%, #112233 60%, #1a3a5c 100%);
        border-radius: 16px;
        padding: 2.2rem 2.5rem;
        margin-bottom: 2rem;
        display: flex;
        align-items: center;
        gap: 2.5rem;
        box-shadow: 0 12px 30px rgba(0, 0, 0, 0.35);
        border: 1px solid rgba(255, 255, 255, 0.1);
        position: relative;
        overflow: hidden;
    }

    .hero-logo-container {
        flex-shrink: 0;
        background: transparent;
        border: none;
        padding: 0;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .hero-logo {
        width: 180px;
        height: 180px;
        object-fit: contain;
        filter: drop-shadow(0 8px 18px rgba(0,0,0,0.55));
    }

    .hero-text {
        display: flex;
        flex-direction: column;
    }

    .hero-title {
        color: #ffffff !important;
        font-weight: 900 !important;
        font-size: 2.4rem !important;
        margin: 0 !important;
        text-transform: uppercase;
        line-height: 1.1;
    }

    .hero-subtitle {
        color: #00d2ff !important;
        margin: 0.5rem 0 0 0 !important;
        font-size: 0.95rem;
        font-weight: 700;
        letter-spacing: 0.15em;
        text-transform: uppercase;
    }

    div[data-testid="stMetric"] {
        background: rgba(15, 23, 42, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.08);
        padding: 14px 16px;
        border-radius: 10px;
    }
    
    div[data-testid="stMetricLabel"] {
        font-size: 0.75rem !important;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #94a3b8 !important;
    }

    div[data-testid="stMetricValue"] {
        font-size: 1.35rem !important;
        font-weight: 800 !important;
        color: #f8fafc !important;
    }

    @media (max-width: 768px) {
        .main .block-container {
            padding-left: 0.75rem !important;
            padding-right: 0.75rem !important;
            padding-top: 1rem !important;
        }

        .hero-header {
            flex-direction: column;
            text-align: center;
            padding: 1.5rem 1rem;
            gap: 1.2rem;
        }

        .hero-logo {
            width: 140px;
            height: 140px;
        }

        .hero-title {
            font-size: 1.8rem !important;
        }

        div[data-testid="stDataFrame"] {
            width: 100% !important;
            overflow-x: auto !important;
        }
    }
    </style>
""", unsafe_allow_html=True)

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


def clean_team_name(text):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    
    if re.search(r"Half time|Kick off|Full time|Round:|P-P", text, re.I):
        return ""
    
    text = re.sub(r"^(?:Round|Week|Matchday)\s*\d+\s*", "", text, flags=re.I)
    text = re.sub(r"\b\d{1,2}:\d{2}\b", "", text)
    
    venues = [
        "Holm Park", "Mossedge Community Pitch", "Nethercraigs Sport Complex",
        "Parklea playing fields", "India Tyres", "New Western Park", "Millburn Park",
        "Renfrew Leisure Centre", "Gray Street Astroturf", "TORYGLEN FOOTBALL CENTRE",
        "Williams Street Football Park", "Cowan Park", "Seedhill Playing Fields",
        "Clydebank Leisure Centre", "Paisley Grammar School"
    ]
    for v in sorted(venues, key=len, reverse=True):
        text = re.sub(r"\b" + re.escape(v) + r"\b", "", text, flags=re.I)

    text = text.strip(" -–:")
    
    if len(text) > 55 or re.search(r"\d+\s*-\s*\d+", text):
        return ""
        
    return text


def norm(x):
    return clean_team_name(x).lower()


def istarget(x):
    n = norm(x)
    return bool(re.search(r"\bbishopton\b.*\bblack\b", n))


def ordinal_date(s):
    s = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", str(s).strip())
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


def parse_matches(url, competition):
    status, final_url, html = fetch(url)
    if status != 200 or not html:
        return empty_df(), {"url": final_url, "http": status, "parsed": 0}

    soup = BeautifulSoup(html, "html.parser")
    out = []

    current_date = None
    current_round = competition

    for element in soup.find_all(['div', 'tr', 'li', 'p']):
        text = re.sub(r"\s+", " ", element.get_text(" ", strip=True)).strip()
        
        date_match = re.search(r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)?,?\s*\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*(?:\s+\d{4})?", text, re.I)
        if date_match and len(text) < 60:
            parsed_dt = ordinal_date(date_match.group(0))
            if parsed_dt:
                current_date = parsed_dt
            rnd_match = re.search(r"Round:\s*([^\s]+)", text, re.I)
            if rnd_match:
                current_round = f"{competition} ({rnd_match.group(1)})"
            continue

        if not current_date:
            continue

        m = re.search(r"^(?P<home>.+?)\s+(?P<hg>\d{1,2})\s*[-–]\s*(?P<ag>\d{1,2})\s+(?P<away>.+?)$", text)
        if not m:
            m = re.search(r"^(?P<home>.+?)\s+(?P<hg>\d{1,2})\s+(?P<ag>\d{1,2})\s+(?P<away>.+?)$", text)
            
        if m:
            h, a = clean_team_name(m.group("home")), clean_team_name(m.group("away"))
            hg, ag = int(m.group("hg")), int(m.group("ag"))
            if h and a and h != a:
                out.append(dict(date=current_date, round=current_round, home=h, away=a,
                                hg=hg, ag=ag, status="FT", competition=competition))
                continue

        m = re.search(r"^(?P<home>.+?)\s+(?P<kick>\d{1,2}:\d{2})\s+(?P<away>.+)$", text)
        if m:
            h, a = clean_team_name(m.group("home")), clean_team_name(m.group("away"))
            if h and a and h != a:
                out.append(dict(date=current_date, round=current_round, home=h, away=a,
                                hg=None, ag=None, status=m.group("kick"), competition=competition))
                continue

        m = re.search(r"^(?P<home>.+?)\s+P-P\s+(?P<away>.+)$", text, re.I)
        if m:
            h, a = clean_team_name(m.group("home")), clean_team_name(m.group("away"))
            if h and a and h != a:
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
    norm_team = norm(team)
    for _, r in df.iterrows():
        if r["status"] != "FT":
            continue
        h_norm, a_norm = norm(r["home"]), norm(r["away"])
        if (istarget(team) and istarget(r["home"])) or h_norm == norm_team:
            gf, ga, opp, venue = int(r["hg"]), int(r["ag"]), r["away"], "H"
        elif (istarget(team) and istarget(r["away"])) or a_norm == norm_team:
            gf, ga, opp, venue = int(r["ag"]), int(r["hg"]), r["home"], "A"
        else:
            continue
        rows.append({"date": r["date"], "opponent": opp, "GF": gf, "GA": ga, "GD": gf-ga,
                     "Result": "W" if gf > ga else "D" if gf == ga else "L", "venue": venue,
                     "competition": r["competition"]})
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

    raw_teams = list(df.home.dropna()) + list(df.away.dropna())
    valid_teams = sorted(list(set([t for t in [clean_team_name(x) for x in raw_teams] if t])))
    
    rows = []
    for t in valid_teams:
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
                    t[team_col] = t[team_col].apply(clean_team_name)
                    t = t[t[team_col] != ""].reset_index(drop=True)
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


def render_fixture_card(r, all_fixtures_df):
    is_home = istarget(r["home"])
    
    if is_home:
        home_team, away_team = "Bishopton FC Black", r["away"]
        home_score, away_score = r["hg"], r["ag"]
        venue = "Home"
    else:
        home_team, away_team = r["home"], "Bishopton FC Black"
        home_score, away_score = r["hg"], r["ag"]
        venue = "Away"

    comp = r["competition"]
    opp = away_team if is_home else home_team
    br, orr = form(all_fixtures_df, "Bishopton FC Black"), form(all_fixtures_df, opp)
    p = win_chance(br, orr, is_home)
    
    if r["status"] == "FT":
        status_display = f"{int(home_score)} - {int(away_score)}"
    else:
        status_display = str(r["status"])

    with st.container(border=True):
        st.markdown(f"**{r['date'].strftime('%a %d %b %Y')}** • *{comp}* • *{venue}*")
        st.markdown(f"**{home_team}** `{status_display}` **{away_team}**")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Bishopton Form", "".join(br.Result.tolist()) if not br.empty else "—")
        c2.metric("Opponent Form", "".join(orr.Result.tolist()) if not orr.empty else "—")
        c3.metric("Win Probability", f"{p:.0%}" if p is not None else "N/A")

        with st.expander("Tactical Form Breakdown"):
            if orr.empty:
                st.write("No recorded games for this opponent.")
            else:
                st.dataframe(format_form_df(orr, ["date", "opponent", "GF", "GA", "Result", "competition"]), hide_index=True, use_container_width=True)


div, cups, diagnostics = load_data()
league = div.get(4, empty_df())

all_dfs = [x for x in list(div.values()) + list(cups.values()) if not x.empty]
all_fixtures_df = pd.concat(all_dfs, ignore_index=True) if all_dfs else empty_df()

st.markdown(f"""
    <div class="hero-header">
        <div class="hero-logo-container">
            <img src="{CLUB_LOGO_URL}" class="hero-logo" onerror="this.onerror=null; this.src='https://img.icons8.com/color/96/football-shirt.png';">
        </div>
        <div class="hero-text">
            <h1 class="hero-title">Bishopton FC Black 2014</h1>
            <p class="hero-subtitle">Official Match Centre & Analytical Hub</p>
        </div>
    </div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ App Controls")
    if st.button("🔄 Sync Live Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    with st.expander("System Engine"):
        st.caption(f"Build Version: {APP_CACHE_VERSION}")
        for item in diagnostics:
            st.write(item)

col_fx, col_tbl = st.columns([1, 1])

with col_fx:
    st.subheader("⚽ Next Immediate Match")
    if all_fixtures_df.empty:
        st.info("No match data currently loaded.")
    else:
        fx_all = all_fixtures_df[all_fixtures_df.home.map(istarget) | all_fixtures_df.away.map(istarget)].sort_values("date")
        upcoming_all = fx_all[fx_all.status != "FT"]

        if upcoming_all.empty:
            st.caption("No upcoming matches scheduled.")
        else:
            render_fixture_card(upcoming_all.iloc[0], all_fixtures_df)

        st.markdown("##### Recent Results")
        completed_all = fx_all[fx_all.status == "FT"].sort_values("date", ascending=False)
        if completed_all.empty:
            st.caption("No completed results recorded yet.")
        else:
            for _, r in completed_all.head(3).iterrows():
                is_home = istarget(r["home"])
                
                if is_home:
                    h_team, a_team = "Bishopton FC Black", r["away"]
                    score = f"{int(r['hg'])} - {int(r['ag'])}"
                else:
                    h_team, a_team = r["home"], "Bishopton FC Black"
                    score = f"{int(r['hg'])} - {int(r['ag'])}"

                with st.container(border=True):
                    st.markdown(f"**{r['date'].strftime('%a %d %b %Y')}** • *{r['competition']}*")
                    st.markdown(f"**{h_team}** `{score}` **{a_team}**")

with col_tbl:
    st.subheader("📊 Division 4 Standings")
    ot, ot_url = official_table()
    tbl_data = ot if ot is not None else calculated_table(league)
    
    st.dataframe(
        tbl_data,
        hide_index=True,
        use_container_width=True,
        height=480
    )
    if ot is not None:
        st.caption("Source: Verified PJDYFL Feed")
    else:
        st.caption("Calculated live standings from parser feed.")

st.divider()

st.header("📅 Division 4 Schedule")
if league.empty:
    st.info("No Division 4 league fixtures available.")
else:
    league_fx = league[league.home.map(istarget) | league.away.map(istarget)].sort_values("date")
    upcoming_league = league_fx[league_fx.status != "FT"]
    
    if upcoming_league.empty:
        st.caption("No upcoming Division 4 league fixtures registered.")
    else:
        initial_five = upcoming_league.head(5)
        remaining_games = upcoming_league.iloc[5:]

        for _, r in initial_five.iterrows():
            render_fixture_card(r, all_fixtures_df)

        if not remaining_games.empty:
            with st.expander(f"➕ Show More Upcoming League Fixtures ({len(remaining_games)} remaining)"):
                for _, r in remaining_games.iterrows():
                    render_fixture_card(r, all_fixtures_df)

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
            render_fixture_card(r, all_fixtures_df)

if not cup_found:
    st.info("No Cup fixtures currently registered for Bishopton FC Black.")
