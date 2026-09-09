import re, math
from datetime import datetime
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
from google import genai

APP_CACHE_VERSION = "v2.7.0"

FILE_ID = "1shpFhmc52QBr1z4eZV0g1g8KIuakU4rv"
CLUB_LOGO_URL = f"https://drive.google.com/thumbnail?id={FILE_ID}&sz=w1000"

SQUAD_SHEET_CSV = "https://docs.google.com/spreadsheets/d/1-XrsLQsx3zxMhAGkTxbMA9DJacIy2xtEgAjiKiRtkLw/export?format=csv"
VIDEO_SHEET_CSV = "https://docs.google.com/spreadsheets/d/1-XrsLQsx3zxMhAGkTxbMA9DJacIy2xtEgAjiKiRtkLw/gviz/tq?tqx=out:csv&sheet=Video%20links"
STATS_SHEET_CSV = "https://docs.google.com/spreadsheets/d/1-XrsLQsx3zxMhAGkTxbMA9DJacIy2xtEgAjiKiRtkLw/gviz/tq?tqx=out:csv&sheet=Match%20Stats"

st.set_page_config(
    page_title="Bishopton FC | Performance Hub",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@500;700;800;900&family=Inter:wght@400;500;600&display=swap');
    
    html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }
    h1, h2, h3, h4, .hero-title { font-family: 'Montserrat', sans-serif !important; letter-spacing: -0.03em; }
    .main .block-container { padding-top: 1.5rem !important; padding-bottom: 2.5rem !important; max-width: 1240px; }

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
    }
    .hero-logo { width: 180px; height: 180px; object-fit: contain; }
    .hero-title { color: #ffffff !important; font-weight: 900 !important; font-size: 2.4rem !important; margin: 0 !important; text-transform: uppercase; }
    .hero-subtitle { color: #00d2ff !important; margin: 0.5rem 0 0 0 !important; font-size: 0.95rem; font-weight: 700; letter-spacing: 0.15em; text-transform: uppercase; }

    div[data-testid="stMetric"] { background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); padding: 14px 16px; border-radius: 10px; }
    div[data-testid="stMetricLabel"] { font-size: 0.75rem !important; font-weight: 700; text-transform: uppercase; color: #94a3b8 !important; }
    div[data-testid="stMetricValue"] { font-size: 1.35rem !important; font-weight: 800 !important; color: #f8fafc !important; }

    .yt-btn {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        background-color: #FF0000;
        color: white !important;
        padding: 0.4rem 0.8rem;
        border-radius: 6px;
        text-decoration: none;
        font-weight: 600;
        font-size: 0.85rem;
        margin-top: 0.5rem;
    }
    .yt-btn:hover { background-color: #CC0000; }
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
COLS = ["date", "round", "home", "away", "hg", "ag", "status", "competition", "youtube_url", "stats"]

def generate_ai_analysis(home_team, away_team, hg, ag, yt_link=""):
    """Calls Gemini API to generate match analysis and estimated statistics."""
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key:
        return "⚠️ Gemini API Key missing in `.streamlit/secrets.toml`."

    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
        Act as a professional football performance analyst. Generate a structured match summary and estimated tactical performance statistics for this completed grassroots match:
        - Home Team: {home_team}
        - Away Team: {away_team}
        - Final Score: {home_team} {hg} - {ag} {away_team}
        - Video Link: {yt_link if yt_link else "Not available"}

        Provide:
        1. A markdown statistics breakdown table containing estimated Total Shots, Shots on Target, Possession %, Corner Kicks, Fouls Committed, and Clearances.
        2. Three concise tactical insights (Attacking Efficiency, Defensive Workrate, Set Pieces).
        """
        
        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"Error generating analysis: {e}"

def clean_team_name(text):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if re.search(r"Half time|Kick off|Full time|Round:|P-P", text, re.I):
        return ""
    text = re.sub(r"^(?:Round|Week|Matchday)\s*\d+\s*", "", text, flags=re.I)
    text = re.sub(r"\b\d{1,2}:\d{2}\b", "", text)
    venues = ["Holm Park", "Mossedge Community Pitch", "Nethercraigs Sport Complex", "Parklea playing fields", "India Tyres", "New Western Park", "Millburn Park", "Renfrew Leisure Centre", "Gray Street Astroturf", "TORYGLEN FOOTBALL CENTRE", "Williams Street Football Park", "Cowan Park", "Seedhill Playing Fields", "Clydebank Leisure Centre", "Paisley Grammar School"]
    for v in sorted(venues, key=len, reverse=True):
        text = re.sub(r"\b" + re.escape(v) + r"\b", "", text, flags=re.I)
    text = text.strip(" -–:")
    if len(text) > 55 or re.search(r"\d+\s*-\s*\d+", text):
        return ""
    return text

def norm(x):
    return clean_team_name(x).lower()

def istarget(x):
    return bool(re.search(r"\bbishopton\b.*\bblack\b", norm(x)))

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

@st.cache_data(ttl=300, show_spinner=False)
def fetch_squad_data(sheet_url, _v=APP_CACHE_VERSION):
    try:
        df = pd.read_csv(sheet_url)
        df.dropna(how="all", inplace=True)
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=300, show_spinner=False)
def fetch_video_links(video_sheet_url, _v=APP_CACHE_VERSION):
    try:
        df = pd.read_csv(video_sheet_url)
        df.dropna(how="all", inplace=True)
        df.columns = [c.strip().lower() for c in df.columns]
        df["parsed_date"] = pd.to_datetime(df["date"].apply(ordinal_date)) if "date" in df.columns else pd.NaT
        df["norm_opp"] = df["opponent"].apply(norm) if "opponent" in df.columns else ""
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=300, show_spinner=False)
def fetch_match_stats(stats_sheet_url, _v=APP_CACHE_VERSION):
    try:
        df = pd.read_csv(stats_sheet_url)
        df.dropna(how="all", inplace=True)
        df.columns = [c.strip().lower() for c in df.columns]
        df["parsed_date"] = pd.to_datetime(df["date"].apply(ordinal_date)) if "date" in df.columns else pd.NaT
        df["norm_opp"] = df["opponent"].apply(norm) if "opponent" in df.columns else ""
        return df
    except Exception:
        return pd.DataFrame()

def parse_matches(url, competition):
    status, final_url, html = fetch(url)
    if status != 200 or not html:
        return pd.DataFrame(columns=COLS), {"url": final_url, "http": status, "parsed": 0}

    soup = BeautifulSoup(html, "html.parser")
    out = []
    current_date, current_round = None, competition

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
                out.append(dict(date=current_date, round=current_round, home=h, away=a, hg=hg, ag=ag, status="FT", competition=competition, youtube_url="", stats=None))
                continue

        m = re.search(r"^(?P<home>.+?)\s+(?P<kick>\d{1,2}:\d{2})\s+(?P<away>.+)$", text)
        if m:
            h, a = clean_team_name(m.group("home")), clean_team_name(m.group("away"))
            if h and a and h != a:
                out.append(dict(date=current_date, round=current_round, home=h, away=a, hg=None, ag=None, status=m.group("kick"), competition=competition, youtube_url="", stats=None))
                continue

    info = {"url": final_url, "http": status, "parsed": len(out)}
    if not out:
        return pd.DataFrame(columns=COLS), info
    df = pd.DataFrame(out, columns=COLS).drop_duplicates(["date", "home", "away", "competition"])
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True), info

def match_youtube_and_stats(fixtures_df, video_df, stats_df):
    if fixtures_df.empty:
        return fixtures_df

    url_col = [c for c in video_df.columns if "youtube" in c or "url" in c or "link" in c] if not video_df.empty else []
    link_column = url_col[0] if url_col else None

    for idx, row in fixtures_df.iterrows():
        f_date = row["date"]
        is_home = istarget(row["home"])
        opp_norm = norm(row["away"] if is_home else row["home"])

        if link_column and not video_df.empty:
            matched_v = video_df[(video_df["parsed_date"] == f_date) | (video_df["norm_opp"].str.contains(opp_norm, regex=False, case=False) & (video_df["norm_opp"] != ""))]
            if not matched_v.empty and pd.notna(matched_v.iloc[0][link_column]):
                fixtures_df.at[idx, "youtube_url"] = str(matched_v.iloc[0][link_column]).strip()

        if not stats_df.empty:
            matched_s = stats_df[(stats_df["parsed_date"] == f_date) | (stats_df["norm_opp"].str.contains(opp_norm, regex=False, case=False) & (stats_df["norm_opp"] != ""))]
            if not matched_s.empty:
                fixtures_df.at[idx, "stats"] = matched_s.iloc[0].to_dict()

    return fixtures_df

@st.cache_data(ttl=300, show_spinner=False)
def load_data(_v=APP_CACHE_VERSION):
    div, cups, diagnostics = {}, {}, []
    video_df = fetch_video_links(VIDEO_SHEET_CSV)
    stats_df = fetch_match_stats(STATS_SHEET_CSV)

    for d, u in DIV_URLS.items():
        try:
            df, info = parse_matches(u, f"Division {d}")
            df = match_youtube_and_stats(df, video_df, stats_df)
            div[d] = df
            diagnostics.append(f"Division {d}: {info}")
        except Exception as e:
            div[d] = pd.DataFrame(columns=COLS)
            diagnostics.append(f"Division {d}: ERROR {type(e).__name__}: {e}")

    for n, u in CUPS.items():
        try:
            df, info = parse_matches(u, n)
            df = match_youtube_and_stats(df, video_df, stats_df)
            cups[n] = df
            diagnostics.append(f"{n}: {info}")
        except Exception as e:
            cups[n] = pd.DataFrame(columns=COLS)
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
        rows.append({"date": r["date"], "opponent": opp, "GF": gf, "GA": ga, "GD": gf-ga, "Result": "W" if gf > ga else "D" if gf == ga else "L", "venue": venue, "competition": r["competition"]})
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
        w, d, l = (r["Result"] == "W").sum(), (r["Result"] == "D").sum(), (r["Result"] == "L").sum()
        gf, ga = r["GF"].sum(), r["GA"].sum()
        rows.append([t, len(r), w, d, l, gf, ga, gf - ga, 3 * w + d])
    return pd.DataFrame(rows, columns=cols).sort_values(["Pts", "GD", "GF"], ascending=False).reset_index(drop=True)

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

def render_fixture_card(r, all_fixtures_df):
    is_home = istarget(r["home"])
    home_team, away_team = ("Bishopton FC Black", r["away"]) if is_home else (r["home"], "Bishopton FC Black")
    venue = "Home" if is_home else "Away"
    opp = away_team if is_home else home_team

    br, orr = form(all_fixtures_df, "Bishopton FC Black"), form(all_fixtures_df, opp)
    p = win_chance(br, orr, is_home)
    status_display = f"{int(r['hg'])} - {int(r['ag'])}" if r["status"] == "FT" else str(r["status"])

    with st.container(border=True):
        st.markdown(f"**{r['date'].strftime('%a %d %b %Y')}** • *{r['competition']}* • *{venue}*")
        st.markdown(f"**{home_team}** `{status_display}` **{away_team}**")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Bishopton Form", "".join(br.Result.tolist()) if not br.empty else "—")
        c2.metric("Opponent Form", "".join(orr.Result.tolist()) if not orr.empty else "—")
        c3.metric("Win Probability", f"{p:.0%}" if p is not None else "N/A")

        col_btn, col_stat = st.columns([1, 1])
        yt_link = str(r.get("youtube_url", "")).strip()
        
        with col_btn:
            if yt_link and yt_link.lower() != "nan":
                st.markdown(f'<a href="{yt_link}" target="_blank" class="yt-btn">▶ Watch Match Footage</a>', unsafe_allow_html=True)

        stats_data = r.get("stats")
        with col_stat:
            if stats_data and isinstance(stats_data, dict):
                with st.expander("📊 Match Statistics"):
                    s_df = pd.DataFrame([
                        {"Category": "Total Shots", "Stat": stats_data.get("shots", "—")},
                        {"Category": "Shots on Target", "Stat": stats_data.get("shots_on_target", "—")},
                        {"Category": "Possession", "Stat": stats_data.get("possession", "—")},
                        {"Category": "Corners", "Stat": stats_data.get("corners", "—")},
                        {"Category": "Fouls", "Stat": stats_data.get("fouls", "—")},
                    ])
                    st.dataframe(s_df, hide_index=True, use_container_width=True)
            elif r["status"] == "FT":
                match_id = f"{r['date'].strftime('%Y%m%d')}_{opp}"
                if st.button("✨ AI Generate Analysis", key=f"ai_{match_id}"):
                    with st.spinner("Generating AI performance analysis..."):
                        analysis = generate_ai_analysis(home_team, away_team, r['hg'], r['ag'], yt_link)
                        st.session_state[f"analysis_{match_id}"] = analysis
                
                if f"analysis_{match_id}" in st.session_state:
                    with st.expander("🤖 AI Match Breakdown", expanded=True):
                        st.markdown(st.session_state[f"analysis_{match_id}"])

div, cups, diagnostics = load_data()
league = div.get(4, pd.DataFrame(columns=COLS))
all_dfs = [x for x in list(div.values()) + list(cups.values()) if not x.empty]
all_fixtures_df = pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame(columns=COLS)

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
                render_fixture_card(r, all_fixtures_df)

with col_tbl:
    st.subheader("📊 Division 4 Standings")
    ot, ot_url = official_table()
    tbl_data = ot if ot is not None else calculated_table(league)
    st.dataframe(tbl_data, hide_index=True, use_container_width=True, height=480)
