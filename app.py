import re
import math
from datetime import datetime

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup


# ============================================================
# APP CONFIGURATION
# ============================================================

APP_CACHE_VERSION = "v2.1.0"

FILE_ID = "1shpFhmc52QBr1z4eZV0g1g8KIuakU4rv"
CLUB_LOGO_URL = f"https://drive.google.com/thumbnail?id={FILE_ID}&sz=w1000"

st.set_page_config(

    page_title="Bishopton FC | Performance Hub",

    page_icon="⚽",

    layout="wide",

 
)


# ============================================================
# CUSTOM CSS
# ============================================================

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
        background: linear-gradient(
            135deg,
            #09131e 0%,
            #112233 60%,
            #1a3a5c 100%
        );
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


# ============================================================
# PJDYFL DATA SOURCES
# ============================================================

BASE = "https://www.pjdyfl.co.uk"

DIV_URLS = {
    i: f"{BASE}/2014-division-{i}"
    for i in range(1, 5)
}

# Current PJDYFL 2014 league table feed
TABLE_URLS = [
    f"{BASE}/leaguetablefeed/1103",
    f"{BASE}/leaguestablefeed/1104"
]

CUPS = {
    "Scottish Cup": f"{BASE}/scottish-cup-2014",
    "League Cup": f"{BASE}/league-cup-2014",
    "PJDYFL Cup": f"{BASE}/pjdyfl-cup-2014",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 Safari/605.1.15"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,*/*;q=0.8"
    ),
    "Cache-Control": "no-cache",
}

COLS = [
    "date",
    "round",
    "home",
    "away",
    "hg",
    "ag",
    "status",
    "competition"
]


# ============================================================
# BASIC HELPERS
# ============================================================

def empty_df():
    return pd.DataFrame(columns=COLS)


def clean_team_name(text):
    text = re.sub(r"\s+", " ", str(text or "")).strip()

    if re.search(
        r"Half time|Kick off|Full time|Round:|P-P",
        text,
        re.I
    ):
        return ""

    text = re.sub(
        r"^(?:Round|Week|Matchday)\s*\d+\s*",
        "",
        text,
        flags=re.I
    )

    text = re.sub(
        r"\b\d{1,2}:\d{2}\b",
        "",
        text
    )

    venues = [
        "Holm Park",
        "Mossedge Community Pitch",
        "Nethercraigs Sport Complex",
        "Parklea playing fields",
        "India Tyres",
        "New Western Park",
        "Millburn Park",
        "Renfrew Leisure Centre",
        "Gray Street Astroturf",
        "TORYGLEN FOOTBALL CENTRE",
        "Williams Street Football Park",
        "Cowan Park",
        "Seedhill Playing Fields",
        "Clydebank Leisure Centre",
        "Paisley Grammar School"
    ]

    for venue in sorted(venues, key=len, reverse=True):
        text = re.sub(
            r"\b" + re.escape(venue) + r"\b",
            "",
            text,
            flags=re.I
        )

    text = text.strip(" -–:")

    if len(text) > 55:
        return ""

    if re.search(r"\d+\s*-\s*\d+", text):
        return ""

    return text


def norm(x):
    return clean_team_name(x).lower()


def istarget(x):
    n = norm(x)

    return bool(
        re.search(
            r"\bbishopton\b.*\bblack\b",
            n
        )
    )


# ============================================================
# DATE PARSING
# ============================================================

def ordinal_date(s):
    s = re.sub(
        r"(\d+)(st|nd|rd|th)",
        r"\1",
        str(s).strip()
    )

    s = re.sub(
        r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s*",
        "",
        s,
        flags=re.I
    )

    for f in (
        "%d %B %Y",
        "%d %b %Y",
        "%d %B",
        "%d %b"
    ):
        try:
            dt = datetime.strptime(s, f)

            if dt.year == 1900:
                dt = dt.replace(year=2026)

            return dt.date()

        except ValueError:
            pass

    return None


# ============================================================
# HTTP FETCH
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def fetch(url, _v=APP_CACHE_VERSION):
    try:
        r = requests.get(
            url,
            headers=HEADERS,
            timeout=15
        )

        return (
            r.status_code,
            r.url,
            r.text
        )

    except Exception:
        return 404, url, ""


# ============================================================
# FIXTURE PARSER
# ============================================================

def parse_matches(url, competition):

    status, final_url, html = fetch(url)

    if status != 200 or not html:
        return empty_df(), {
            "url": final_url,
            "http": status,
            "parsed": 0
        }

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    out = []

    current_date = None
    current_round = competition

    # --------------------------------------------------------
    # Walk through all likely content elements
    # --------------------------------------------------------

    for element in soup.find_all(
        ["div", "tr", "li", "p"]
    ):

        text = re.sub(
            r"\s+",
            " ",
            element.get_text(" ", strip=True)
        ).strip()

        if not text:
            continue

        # ----------------------------------------------------
        # DATE
        # ----------------------------------------------------

        date_match = re.search(
            r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)?"
            r",?\s*"
            r"\d{1,2}(?:st|nd|rd|th)?"
            r"\s+"
            r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
            r"[a-z]*"
            r"(?:\s+\d{4})?",
            text,
            re.I
        )

        if date_match and len(text) < 80:

            parsed_dt = ordinal_date(
                date_match.group(0)
            )

            if parsed_dt:

                current_date = parsed_dt

                rnd_match = re.search(
                    r"Round:\s*([^\s]+)",
                    text,
                    re.I
                )

                if rnd_match:
                    current_round = (
                        f"{competition} "
                        f"({rnd_match.group(1)})"
                    )

                continue

        if not current_date:
            continue

        # ----------------------------------------------------
        # REMOVE NON-FIXTURE METADATA
        # ----------------------------------------------------

        fixture_text = re.sub(
            r"\s+Half time score:.*$",
            "",
            text,
            flags=re.I
        )

        fixture_text = re.sub(
            r"\s+Kick off time:.*$",
            "",
            fixture_text,
            flags=re.I
        )

        fixture_text = re.sub(
            r"\s+Venue:.*$",
            "",
            fixture_text,
            flags=re.I
        )

        fixture_text = re.sub(
            r"\s+P-P\b.*$",
            " P-P",
            fixture_text,
            flags=re.I
        )

        fixture_text = re.sub(
            r"\s+",
            " ",
            fixture_text
        ).strip()

        # ----------------------------------------------------
        # COMPLETED MATCH
        #
        # Example:
        #
        # Team A 3 - 2 Team B
        #
        # or:
        #
        # Team A 3 2 Team B
        # ----------------------------------------------------

        m = re.search(
            r"^(?P<home>.+?)\s+"
            r"(?P<hg>\d{1,2})\s*[-–]\s*"
            r"(?P<ag>\d{1,2})\s+"
            r"(?P<away>.+?)$",
            fixture_text
        )

        if not m:

            m = re.search(
                r"^(?P<home>.+?)\s+"
                r"(?P<hg>\d{1,2})\s+"
                r"(?P<ag>\d{1,2})\s+"
                r"(?P<away>.+?)$",
                fixture_text
            )

        if m:

            h = clean_team_name(
                m.group("home")
            )

            a = clean_team_name(
                m.group("away")
            )

            if (
                h
                and a
                and h.lower() != a.lower()
            ):

                out.append({
                    "date": current_date,
                    "round": current_round,
                    "home": h,
                    "away": a,
                    "hg": int(m.group("hg")),
                    "ag": int(m.group("ag")),
                    "status": "FT",
                    "competition": competition
                })

                continue

        # ----------------------------------------------------
        # UPCOMING FIXTURE
        #
        # PJDYFL can effectively present this as:
        #
        # Team A 09:00 Team B
        #
        # or:
        #
        # Team A09:00Team B
        # ----------------------------------------------------

        m = re.search(
            r"^(?P<home>.+?)\s*"
            r"(?P<kick>\d{1,2}:\d{2})\s*"
            r"(?P<away>.+?)$",
            fixture_text
        )

        if m:

            h = clean_team_name(
                m.group("home")
            )

            a = clean_team_name(
                m.group("away")
            )

            if (
                h
                and a
                and h.lower() != a.lower()
            ):

                out.append({
                    "date": current_date,
                    "round": current_round,
                    "home": h,
                    "away": a,
                    "hg": None,
                    "ag": None,
                    "status": m.group("kick"),
                    "competition": competition
                })

                continue

        # ----------------------------------------------------
        # POSTPONED FIXTURE
        # ----------------------------------------------------

        m = re.search(
            r"^(?P<home>.+?)\s+P-P\s+"
            r"(?P<away>.+?)$",
            fixture_text,
            re.I
        )

        if m:

            h = clean_team_name(
                m.group("home")
            )

            a = clean_team_name(
                m.group("away")
            )

            if (
                h
                and a
                and h.lower() != a.lower()
            ):

                out.append({
                    "date": current_date,
                    "round": current_round,
                    "home": h,
                    "away": a,
                    "hg": None,
                    "ag": None,
                    "status": "Postponed",
                    "competition": competition
                })

    # --------------------------------------------------------
    # PARSER RESULT
    # --------------------------------------------------------

    info = {
        "url": final_url,
        "http": status,
        "parsed": len(out)
    }

    if not out:
        return empty_df(), info

    df = pd.DataFrame(
        out,
        columns=COLS
    )

    df = df.drop_duplicates(
        [
            "date",
            "home",
            "away",
            "competition"
        ]
    )

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    df = df.dropna(
        subset=["date"]
    )

    return (
        df.sort_values(
            ["date", "home"],
            ascending=[True, True]
        )
        .reset_index(drop=True),
        info
    )


# ============================================================
# LOAD ALL FIXTURES
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def load_data(_v=APP_CACHE_VERSION):

    div = {}
    cups = {}
    diagnostics = []

    # --------------------------------------------------------
    # DIVISIONS
    # --------------------------------------------------------

    for d, url in DIV_URLS.items():

        try:

            df, info = parse_matches(
                url,
                f"Division {d}"
            )

            div[d] = df

            diagnostics.append(
                f"Division {d}: {info}"
            )

        except Exception as e:

            div[d] = empty_df()

            diagnostics.append(
                f"Division {d}: ERROR "
                f"{type(e).__name__}: {e}"
            )

    # --------------------------------------------------------
    # CUPS
    # --------------------------------------------------------

    for name, url in CUPS.items():

        try:

            df, info = parse_matches(
                url,
                name
            )

            cups[name] = df

            diagnostics.append(
                f"{name}: {info}"
            )

        except Exception as e:

            cups[name] = empty_df()

            diagnostics.append(
                f"{name}: ERROR "
                f"{type(e).__name__}: {e}"
            )

    return (
        div,
        cups,
        diagnostics
    )


# ============================================================
# RESULTS
# ============================================================

def results(df, team):

    cols = [
        "date",
        "opponent",
        "GF",
        "GA",
        "GD",
        "Result",
        "venue",
        "competition"
    ]

    if df.empty:
        return pd.DataFrame(columns=cols)

    rows = []

    norm_team = norm(team)

    for _, r in df.iterrows():

        if r["status"] != "FT":
            continue

        h_norm = norm(r["home"])
        a_norm = norm(r["away"])

        if (
            (istarget(team) and istarget(r["home"]))
            or h_norm == norm_team
        ):

            gf = int(r["hg"])
            ga = int(r["ag"])
            opp = r["away"]
            venue = "H"

        elif (
            (istarget(team) and istarget(r["away"]))
            or a_norm == norm_team
        ):

            gf = int(r["ag"])
            ga = int(r["hg"])
            opp = r["home"]
            venue = "A"

        else:
            continue

        rows.append({
            "date": r["date"],
            "opponent": opp,
            "GF": gf,
            "GA": ga,
            "GD": gf - ga,
            "Result": (
                "W"
                if gf > ga
                else "D"
                if gf == ga
                else "L"
            ),
            "venue": venue,
            "competition": r["competition"]
        })

    if not rows:
        return pd.DataFrame(columns=cols)

    return (
        pd.DataFrame(rows, columns=cols)
        .sort_values(
            "date",
            ascending=False
        )
        .reset_index(drop=True)
    )


def form(df, team, n=5):
    return results(df, team).head(n)


# ============================================================
# STRENGTH / WIN PROBABILITY
# ============================================================

def strength(r):

    if r.empty:
        return None

    def ppg(x):

        return (
            3 * (x.Result == "W").sum()
            + (x.Result == "D").sum()
        ) / len(x)

    recent = r.head(5)

    return (
        .55 * ppg(r)
        + .30 * ppg(recent)
        + .15 * (
            1
            + math.tanh(
                recent.GD.mean() / 3
            )
        )
    )


def win_chance(a, b, home=True):

    sa = strength(a)
    sb = strength(b)

    if sa is None or sb is None:
        return None

    x = (
        sa
        - sb
        + (
            0.18
            if home
            else -0.02
        )
    )

    return max(
        .05,
        min(
            .95,
            1 / (
                1
                + math.exp(-1.35 * x)
            )
        )
    )


# ============================================================
# CALCULATED TABLE FALLBACK
# ============================================================

def calculated_table(df):

    cols = [
        "Team",
        "P",
        "W",
        "D",
        "L",
        "GF",
        "GA",
        "GD",
        "Pts"
    ]

    if (
        df.empty
        or not {
            "home",
            "away"
        }.issubset(df.columns)
    ):
        return pd.DataFrame(columns=cols)

    raw_teams = (
        list(df.home.dropna())
        + list(df.away.dropna())
    )

    valid_teams = sorted(
        list(
            set(
                [
                    clean_team_name(x)
                    for x in raw_teams
                    if clean_team_name(x)
                ]
            )
        )
    )

    rows = []

    for team in valid_teams:

        r = results(
            df,
            team
        )

        if r.empty:

            rows.append([
                team,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0
            ])

            continue

        w = (
            r["Result"] == "W"
        ).sum()

        d = (
            r["Result"] == "D"
        ).sum()

        l = (
            r["Result"] == "L"
        ).sum()

        gf = r["GF"].sum()
        ga = r["GA"].sum()
        gd = gf - ga
        pts = 3 * w + d

        rows.append([
            team,
            len(r),
            w,
            d,
            l,
            gf,
            ga,
            gd,
            pts
        ])

    return (
        pd.DataFrame(
            rows,
            columns=cols
        )
        .sort_values(
            ["Pts", "GD", "GF"],
            ascending=False
        )
        .reset_index(drop=True)
    )


# ============================================================
# OFFICIAL PJDYFL TABLE
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def official_table(_v=APP_CACHE_VERSION):

    # The current PJDYFL 2014 table feed
    url = f"{BASE}/leaguetablefeed/1103"

    try:

        status, final_url, html = fetch(url)

        if (
            status != 200
            or not html
        ):
            return None, None

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        # ----------------------------------------------------
        # Locate Division 4
        # ----------------------------------------------------

        heading = None

        for heading_tag in soup.find_all(
            ["h2", "h3", "h4", "h5"]
        ):

            heading_text = heading_tag.get_text(
                " ",
                strip=True
            )

            if re.search(
                r"2014\s+Division\s+4",
                heading_text,
                re.I
            ):

                heading = heading_tag
                break

        # ----------------------------------------------------
        # If heading wasn't found, inspect tables directly
        # ----------------------------------------------------

        tables = soup.find_all("table")

        if heading is not None:

            table = heading.find_next("table")

            if table is not None:
                tables = [table] + [
                    t for t in tables
                    if t is not table
                ]

        # ----------------------------------------------------
        # Parse candidate tables
        # ----------------------------------------------------

        for table in tables:

            rows = []

            for tr in table.find_all("tr"):

                cells = [
                    c.get_text(
                        " ",
                        strip=True
                    )
                    for c in tr.find_all(
                        ["th", "td"]
                    )
                ]

                if cells:
                    rows.append(cells)

            if len(rows) < 2:
                continue

            # ------------------------------------------------
            # Find header row
            # ------------------------------------------------

            header_index = None

            for i, row in enumerate(rows[:5]):

                joined = " ".join(
                    str(x).lower()
                    for x in row
                )

                if (
                    "club" in joined
                    or "team" in joined
                ) and (
                    "pts" in joined
                    or "points" in joined
                ):

                    header_index = i
                    break

            if header_index is None:
                continue

            headers = [
                str(x).strip()
                for x in rows[header_index]
            ]

            data = rows[
                header_index + 1:
            ]

            data = [
                row
                for row in data
                if len(row) == len(headers)
            ]

            if not data:
                continue

            df = pd.DataFrame(
                data,
                columns=headers
            )

            # ------------------------------------------------
            # Normalise column names
            # ------------------------------------------------

            rename_map = {}

            for col in df.columns:

                c = str(col).strip().lower()

                if c in [
                    "club",
                    "team",
                    "club/team"
                ]:
                    rename_map[col] = "Team"

                elif c in [
                    "p",
                    "pl",
                    "played"
                ]:
                    rename_map[col] = "P"

                elif c in [
                    "w",
                    "won"
                ]:
                    rename_map[col] = "W"

                elif c in [
                    "d",
                    "drawn"
                ]:
                    rename_map[col] = "D"

                elif c in [
                    "l",
                    "lost"
                ]:
                    rename_map[col] = "L"

                elif c in [
                    "gf",
                    "for"
                ]:
                    rename_map[col] = "GF"

                elif c in [
                    "ga",
                    "against"
                ]:
                    rename_map[col] = "GA"

                elif c in [
                    "gd",
                    "difference"
                ]:
                    rename_map[col] = "GD"

                elif c in [
                    "pts",
                    "points"
                ]:
                    rename_map[col] = "Pts"

            df = df.rename(
                columns=rename_map
            )

            if "Team" not in df.columns:
                continue

            # ------------------------------------------------
            # Clean team names
            # ------------------------------------------------

            df["Team"] = df["Team"].apply(
                clean_team_name
            )

            df = df[
                df["Team"] != ""
            ].copy()

            # ------------------------------------------------
            # Numeric columns
            # ------------------------------------------------

            for col in [
                "P",
                "W",
                "D",
                "L",
                "GF",
                "GA",
                "GD",
                "Pts"
            ]:

                if col in df.columns:

                    df[col] = pd.to_numeric(
                        df[col],
                        errors="coerce"
                    )

            # ------------------------------------------------
            # If GD isn't supplied, calculate it
            # ------------------------------------------------

            if (
                "GD" not in df.columns
                and "GF" in df.columns
                and "GA" in df.columns
            ):

                df["GD"] = (
                    df["GF"]
                    - df["GA"]
                )

            # ------------------------------------------------
            # Sort official table
            # ------------------------------------------------

            sort_cols = []

            if "Pts" in df.columns:
                sort_cols.append("Pts")

            if "GD" in df.columns:
                sort_cols.append("GD")

            if "GF" in df.columns:
                sort_cols.append("GF")

            if sort_cols:

                df = df.sort_values(
                    sort_cols,
                    ascending=False
                )

            df = df.reset_index(
                drop=True
            )

            # ------------------------------------------------
            # Make numeric columns integers where possible
            # ------------------------------------------------

            for col in [
                "P",
                "W",
                "D",
                "L",
                "GF",
                "GA",
                "GD",
                "Pts"
            ]:

                if col in df.columns:

                    df[col] = (
                        df[col]
                        .fillna(0)
                        .astype(int)
                    )

            return df, final_url

        return None, None

    except Exception:
        return None, None


# ============================================================
# DISPLAY HELPERS
# ============================================================

def format_form_df(
    df_in,
    display_cols
):

    if df_in.empty:
        return pd.DataFrame(
            columns=display_cols
        )

    df_out = df_in[
        display_cols
    ].copy()

    if "date" in df_out.columns:

        df_out["date"] = (
            pd.to_datetime(
                df_out["date"],
                errors="coerce"
            )
            .dt.strftime("%d/%m")
        )

    return df_out


# ============================================================
# FIXTURE CARD
# ============================================================

def render_fixture_card(
    r,
    all_fixtures_df
):

    is_home = istarget(
        r["home"]
    )

    if is_home:

        home_team = "Bishopton FC Black"
        away_team = r["away"]

        home_score = r["hg"]
        away_score = r["ag"]

        venue = "Home"

    else:

        home_team = r["home"]
        away_team = "Bishopton FC Black"

        home_score = r["hg"]
        away_score = r["ag"]

        venue = "Away"

    comp = r["competition"]

    opponent = (
        away_team
        if is_home
        else home_team
    )

    bishopton_form = form(
        all_fixtures_df,
        "Bishopton FC Black"
    )

    opponent_form = form(
        all_fixtures_df,
        opponent
    )

    p = win_chance(
        bishopton_form,
        opponent_form,
        is_home
    )

    # --------------------------------------------------------
    # Match status
    # --------------------------------------------------------

    if r["status"] == "FT":

        status_display = (
            f"{int(home_score)} - "
            f"{int(away_score)}"
        )

    else:

        status_display = str(
            r["status"]
        )

    # --------------------------------------------------------
    # Card
    # --------------------------------------------------------

    with st.container(border=True):

        st.markdown(
            f"**{r['date'].strftime('%a %d %b %Y')}** "
            f"• *{comp}* • *{venue}*"
        )

        st.markdown(
            f"**{home_team}** "
            f"`{status_display}` "
            f"**{away_team}**"
        )

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Bishopton Form",
            (
                "".join(
                    bishopton_form.Result.tolist()
                )
                if not bishopton_form.empty
                else "—"
            )
        )

        c2.metric(
            "Opponent Form",
            (
                "".join(
                    opponent_form.Result.tolist()
                )
                if not opponent_form.empty
                else "—"
            )
        )

        c3.metric(
            "Win Probability",
            (
                f"{p:.0%}"
                if p is not None
                else "N/A"
            )
        )

        with st.expander(
            "Tactical Form Breakdown"
        ):

            if opponent_form.empty:

                st.write(
                    "No recorded games for this opponent."
                )

            else:

                st.dataframe(
                    format_form_df(
                        opponent_form,
                        [
                            "date",
                            "opponent",
                            "GF",
                            "GA",
                            "Result",
                            "competition"
                        ]
                    ),
                    hide_index=True,
                    use_container_width=True
                )


# ============================================================
# LOAD DATA
# ============================================================

div, cups, diagnostics = load_data()

# Division 4 is the team's league
league = div.get(
    4,
    empty_df()
)

# Combine all available fixtures
all_dfs = [
    x
    for x in (
        list(div.values())
        + list(cups.values())
    )
    if not x.empty
]

if all_dfs:

    all_fixtures_df = pd.concat(
        all_dfs,
        ignore_index=True
    )

else:

    all_fixtures_df = empty_df()


# ============================================================
# HERO
# ============================================================

st.markdown(
    f"""
    <div class="hero-header">
        <div class="hero-logo-container">
            <img
                src="{CLUB_LOGO_URL}"
                class="hero-logo"
                onerror="this.onerror=null;
                this.src='https://img.icons8.com/color/96/football-shirt.png';"
            >
        </div>

        <div class="hero-text">

            <h1 class="hero-title">
                Bishopton FC Black 2014
            </h1>

            <p class="hero-subtitle">
                Official Match Centre & Analytical Hub
            </p>

        </div>
    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header(
        "⚙️ App Controls"
    )

    if st.button(
        "🔄 Sync Live Data",
        use_container_width=True
    ):

        st.cache_data.clear()
        st.rerun()

    with st.expander(
        "System Engine"
    ):

        st.caption(
            f"Build Version: "
            f"{APP_CACHE_VERSION}"
        )

        for item in diagnostics:
            st.write(item)


# ============================================================
# TOP TWO COLUMNS
# ============================================================

col_fx, col_tbl = st.columns(
    [1, 1]
)


# ============================================================
# NEXT MATCH / RECENT RESULTS
# ============================================================

with col_fx:

    st.subheader(
        "⚽ Next Immediate Match"
    )

    if all_fixtures_df.empty:

        st.info(
            "No match data currently loaded."
        )

    else:

        # ----------------------------------------------------
        # All Bishopton fixtures
        # ----------------------------------------------------

        fx_all = (
            all_fixtures_df[
                all_fixtures_df.home.map(istarget)
                | all_fixtures_df.away.map(istarget)
            ]
            .sort_values(
                "date"
            )
        )

        # ----------------------------------------------------
        # UPCOMING FIXTURES
        #
        # Important:
        # We now use the date as well as FT status.
        # ----------------------------------------------------

        today = pd.Timestamp.now().normalize()

        upcoming_all = fx_all[
            (
                fx_all["date"]
                >= today
            )
            &
            (
                fx_all["status"]
                != "FT"
            )
        ].sort_values(
            "date"
        )

        if upcoming_all.empty:

            st.caption(
                "No upcoming matches scheduled."
            )

        else:

            render_fixture_card(
                upcoming_all.iloc[0],
                all_fixtures_df
            )

        # ----------------------------------------------------
        # RECENT RESULTS
        # ----------------------------------------------------

        st.markdown(
            "##### Recent Results"
        )

        completed_all = (
            fx_all[
                fx_all.status == "FT"
            ]
            .sort_values(
                "date",
                ascending=False
            )
        )

        if completed_all.empty:

            st.caption(
                "No completed results recorded yet."
            )

        else:

            for _, r in completed_all.head(3).iterrows():

                is_home = istarget(
                    r["home"]
                )

                if is_home:

                    h_team = "Bishopton FC Black"
                    a_team = r["away"]

                    score = (
                        f"{int(r['hg'])} - "
                        f"{int(r['ag'])}"
                    )

                else:

                    h_team = r["home"]
                    a_team = "Bishopton FC Black"

                    score = (
                        f"{int(r['hg'])} - "
                        f"{int(r['ag'])}"
                    )

                with st.container(
                    border=True
                ):

                    st.markdown(
                        f"**{r['date'].strftime('%a %d %b %Y')}** "
                        f"• *{r['competition']}*"
                    )

                    st.markdown(
                        f"**{h_team}** "
                        f"`{score}` "
                        f"**{a_team}**"
                    )


# ============================================================
# LEAGUE TABLE
# ============================================================

with col_tbl:

    st.subheader(
        "📊 Division 4 Standings"
    )

    official, official_url = official_table()

    if official is not None and not official.empty:

        tbl_data = official

    else:

        tbl_data = calculated_table(
            league
        )

    # --------------------------------------------------------
    # Display
    # --------------------------------------------------------

    if tbl_data.empty:

        st.warning(
            "League table could not currently be loaded."
        )

    else:

        st.dataframe(
            tbl_data,
            hide_index=True,
            use_container_width=True,
            height=480
        )

        if official is not None:

            st.caption(
                "Source: Verified PJDYFL Feed"
            )

        else:

            st.caption(
                "Calculated live standings "
                "from parser feed."
            )


# ============================================================
# DIVISION 4 SCHEDULE
# ============================================================

st.divider()

st.header(
    "📅 Division 4 Schedule"
)

if league.empty:

    st.info(
        "No Division 4 league fixtures available."
    )

else:

    league_fx = (
        league[
            league.home.map(istarget)
            | league.away.map(istarget)
        ]
        .sort_values(
            "date"
        )
    )

    today = pd.Timestamp.now().normalize()

    upcoming_league = league_fx[
        (
            league_fx["date"]
            >= today
        )
        &
        (
            league_fx["status"]
            != "FT"
        )
    ].sort_values(
        "date"
    )

    if upcoming_league.empty:

        st.caption(
            "No upcoming Division 4 "
            "league fixtures registered."
        )

    else:

        initial_five = (
            upcoming_league.head(5)
        )

        remaining_games = (
            upcoming_league.iloc[5:]
        )

        # ----------------------------------------------------
        # First five
        # ----------------------------------------------------

        for _, r in initial_five.iterrows():

            render_fixture_card(
                r,
                all_fixtures_df
            )

        # ----------------------------------------------------
        # Remaining games
        # ----------------------------------------------------

        if not remaining_games.empty:

            with st.expander(
                "➕ Show More Upcoming "
                f"League Fixtures "
                f"({len(remaining_games)} remaining)"
            ):

                for _, r in remaining_games.iterrows():

                    render_fixture_card(
                        r,
                        all_fixtures_df
                    )


# ============================================================
# CUP COMPETITIONS
# ============================================================

st.divider()

st.header(
    "🏆 Cup Competitions"
)

cup_found = False

for cup_name, cdf in cups.items():

    if cdf.empty:
        continue

    cfx = cdf[
        cdf.home.map(istarget)
        | cdf.away.map(istarget)
    ]

    if cfx.empty:
        continue

    cup_found = True

    st.subheader(
        cup_name
    )

    # --------------------------------------------------------
    # Separate upcoming and completed cups
    # --------------------------------------------------------

    today = pd.Timestamp.now().normalize()

    upcoming_cup = cfx[
        (
            cfx["date"]
            >= today
        )
        &
        (
            cfx["status"]
            != "FT"
        )
    ].sort_values(
        "date"
    )

    completed_cup = cfx[
        cfx["status"] == "FT"
    ].sort_values(
        "date",
        ascending=False
    )

    # Upcoming first
    for _, r in upcoming_cup.iterrows():

        render_fixture_card(
            r,
            all_fixtures_df
        )

    # Then completed
    for _, r in completed_cup.iterrows():

        render_fixture_card(
            r,
            all_fixtures_df
        )


if not cup_found:

    st.info(
        "No Cup fixtures currently "
        "registered for Bishopton FC Black."
    )
