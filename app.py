import re, math
from datetime import datetime
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

st.set_page_config(page_title="Bishopton FC Fixture & Form Guide", page_icon="⚽", layout="wide")

BASE="https://www.pjdyfl.co.uk"
TARGET="Bishopton FC Black (2014)"
DIV_URLS={i:f"{BASE}/2014-division-{i}" for i in range(1,5)}
LEAGUE_URL=DIV_URLS[4]
TABLE_URLS=[f"{BASE}/leaguestablefeed/1104", f"{BASE}/leaguetablefeed/1103"]
CUPS={"Scottish Cup":f"{BASE}/scottish-cup-2014","League Cup":f"{BASE}/league-cup-2014"}
HEADERS={"User-Agent":"Mozilla/5.0 BishoptonFCFixtureGuide/1.0"}

def clean(x): return re.sub(r"\s+"," ",str(x or "")).strip()
def norm(x): return clean(x).lower()
def istarget(x): return norm(x).startswith("bishopton fc black")
def ordinal_date(s):
    s=re.sub(r"(\d+)(st|nd|rd|th)",r"\1",clean(s))
    for f in ("%A, %d %B %Y","%d %B %Y"):
        try:return datetime.strptime(s,f).date()
        except:pass
    return None

@st.cache_data(ttl=900,show_spinner=False)
def page(url):
    r=requests.get(url,headers=HEADERS,timeout=30); r.raise_for_status(); return r.text

def parse_matches(url,competition):
    soup=BeautifulSoup(page(url),"html.parser")
    lines=[clean(x) for x in soup.get_text("\n").splitlines() if clean(x)]
    date=None; rnd=""; out=[]
    date_re=re.compile(r"^(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+\d{1,2}(?:st|nd|rd|th)\s+\w+\s+\d{4}$")
    round_re=re.compile(r"^Round:\s*(.*)$")
    # PJDYFL currently renders the score/time immediately after the home-team name
    # (e.g. "Bishopton FC Black (2014)3 2 Bridge...") so the separator before
    # the first number is not guaranteed to be whitespace.
    score_patterns=[
        re.compile(r"^(.*?\))\s*(\d+)\s+(\d+)\s+(.*?)(?:Half time score:|Kick off time:|$)"),
        re.compile(r"^(.*?)\s+(\d+)\s+(\d+)\s+(.*?)(?:Half time score:|Kick off time:|$)")
    ]
    time_patterns=[
        re.compile(r"^(.*?\))\s*(\d{1,2}:\d{2})\s+(.*)$"),
        re.compile(r"^(.*?)\s+(\d{1,2}:\d{2})\s+(.*)$")
    ]
    for line in lines:
        if date_re.match(line): date=ordinal_date(line); continue
        m=round_re.match(line)
        if m: rnd=m.group(1); continue
        if not date: continue
        if "P-P" in line.upper():
            a=re.split(r"\s+P-P\s+",line,maxsplit=1,flags=re.I)
            if len(a)==2:
                out.append(dict(date=date,round=rnd,home=clean(a[0]),away=clean(a[1].split("Kick off time:")[0]),hg=None,ag=None,status="Postponed",competition=competition))
            continue
        matched=False
        for pat in score_patterns:
            m=pat.match(line)
            if m:
                home,hg,ag,away=clean(m.group(1)),int(m.group(2)),int(m.group(3)),clean(m.group(4))
                if home and away and len(home)<100 and len(away)<100:
                    out.append(dict(date=date,round=rnd,home=home,away=away,hg=hg,ag=ag,status="FT",competition=competition)); matched=True; break
        if matched: continue
        for pat in time_patterns:
            m=pat.match(line)
            if m:
                home,kick,away=clean(m.group(1)),m.group(2),clean(m.group(3))
                if home and away and len(home)<100 and len(away)<100:
                    out.append(dict(date=date,round=rnd,home=home,away=away,hg=None,ag=None,status=kick,competition=competition)); break
    if not out:return pd.DataFrame(columns=["date","round","home","away","hg","ag","status","competition"])
    df=pd.DataFrame(out).drop_duplicates(["date","home","away","competition","round"])
    df["date"]=pd.to_datetime(df.date)
    return df.sort_values("date").reset_index(drop=True)

@st.cache_data(ttl=900,show_spinner=False)
def load_data():
    div={}; errors=[]
    for d,u in DIV_URLS.items():
        try: div[d]=parse_matches(u,f"Division {d}")
        except Exception as e: div[d]=pd.DataFrame(columns=["date","round","home","away","hg","ag","status","competition"]); errors.append(f"Division {d}: {e}")
    cups={}
    for n,u in CUPS.items():
        try:cups[n]=parse_matches(u,n)
        except Exception as e:cups[n]=pd.DataFrame(columns=["date","round","home","away","hg","ag","status","competition"]); errors.append(f"{n}: {e}")
    return div,cups,errors

def results(df,team):
    if df.empty:return pd.DataFrame()
    rows=[]
    for _,r in df.iterrows():
        if r.status!="FT":continue
        if norm(r.home)==norm(team):
            gf,ga,opp,venue=int(r.hg),int(r.ag),r.away,"H"
        elif norm(r.away)==norm(team):
            gf,ga,opp,venue=int(r.ag),int(r.hg),r.home,"A"
        else:continue
        rows.append({"date":r.date,"opponent":opp,"GF":gf,"GA":ga,"GD":gf-ga,
                     "Result":"W" if gf>ga else "D" if gf==ga else "L","venue":venue,
                     "competition":r.competition})
    return pd.DataFrame(rows).sort_values("date",ascending=False) if rows else pd.DataFrame()

def form(df,team,n=5):
    r=results(df,team).head(n)
    return r

def strength(r):
    if r.empty:return None
    def ppg(x):return (3*(x.Result=="W").sum()+(x.Result=="D").sum())/len(x)
    recent=r.head(5)
    return .55*ppg(r)+.30*ppg(recent)+.15*(1+math.tanh(recent.GD.mean()/3))

def win_chance(a,b,home=True):
    sa,sb=strength(a),strength(b)
    if sa is None or sb is None:return None
    x=sa-sb+(0.18 if home else -0.02)
    return max(.05,min(.95,1/(1+math.exp(-1.35*x))))

def calculated_table(df):
    required={"home","away"}
    if df.empty or not required.issubset(df.columns):
        return pd.DataFrame(columns=["Team","P","W","D","L","GF","GA","GD","Pts"])
    teams=set(df.home.dropna())|set(df.away.dropna()); rows=[]
    for t in teams:
        r=results(df,t)
        w=(r.Result=="W").sum(); d=(r.Result=="D").sum(); l=(r.Result=="L").sum()
        rows.append([t,len(r),w,d,l,r.GF.sum(),r.GA.sum(),r.GD.sum(),3*w+d])
    return pd.DataFrame(rows,columns=["Team","P","W","D","L","GF","GA","GD","Pts"]).sort_values(["Pts","GD","GF"],ascending=False).reset_index(drop=True)

def official_table():
    for url in TABLE_URLS:
        try:
            tabs=pd.read_html(page(url))
            for t in tabs:
                cols=[str(c).strip().lower() for c in t.columns]
                joined=" ".join(cols)
                if len(t)>=5 and ("club" in joined or "team" in joined) and "pts" in joined:
                    return t, url
        except Exception:
            continue
    return None, None

div,cups,load_errors=load_data()
league=div.get(4,pd.DataFrame())
all_div=pd.concat([x for x in div.values() if not x.empty],ignore_index=True) if any(not x.empty for x in div.values()) else pd.DataFrame()

st.title("⚽ Bishopton FC Black 2014 — Fixtures & Form Guide")
st.caption("Live PJDYFL data • estimates are statistical guides, not betting odds")

with st.sidebar:
    st.header("Data")
    if st.button("🔄 Refresh PJDYFL data"):
        st.cache_data.clear(); st.rerun()
    st.write("Sources: PJDYFL 2014 Divisions 1–4, Scottish Cup and League Cup.")
    if load_errors:
        with st.expander("Data-source diagnostics"):
            for err in load_errors: st.write(err)

st.header("🏆 Division 4")
st.subheader("Bishopton FC Black fixtures")
if league.empty: st.error("Could not load Division 4.")
else:
    fx=league[league.home.map(istarget)|league.away.map(istarget)].sort_values("date")
    for _,r in fx.iterrows():
        opp=r.away if istarget(r.home) else r.home
        home=istarget(r.home)
        score=f"{int(r.hg)}–{int(r.ag)}" if r.status=="FT" else r.status
        st.markdown(f"### {r.date.strftime('%a %d %b %Y')} — {'Home' if home else 'Away'}")
        st.markdown(f"**Bishopton FC Black** vs **{opp}** — **{score}**")
        br,orr=form(league,TARGET),form(league,opp)
        p=win_chance(br,orr,home)
        c1,c2,c3=st.columns(3)
        c1.metric("Bishopton last 5","".join(br.Result.tolist()) if not br.empty else "—")
        c2.metric("Opponent last 5","".join(orr.Result.tolist()) if not orr.empty else "—")
        c3.metric("Estimated Bishopton win chance",f"{p:.0%}" if p is not None else "N/A")
        with st.expander("Form guide"):
            a,b=st.columns(2)
            with a:
                st.write("**Bishopton FC Black**")
                st.dataframe(br[["date","opponent","GF","GA","Result"]].assign(date=lambda x:x.date.dt.strftime("%d/%m/%Y")),hide_index=True,use_container_width=True)
            with b:
                st.write(f"**{opp}**")
                st.dataframe(orr[["date","opponent","GF","GA","Result"]].assign(date=lambda x:x.date.dt.strftime("%d/%m/%Y")),hide_index=True,use_container_width=True)
            st.caption("Estimate uses season points-per-game, last-five form, goal difference and a small home advantage.")
        st.divider()

st.subheader("Division 4 League Table")
ot,ot_url=official_table()
if ot is not None:
    st.dataframe(ot,hide_index=True,use_container_width=True)
    st.caption(f"Official PJDYFL league table source: {ot_url}")
else:
    st.dataframe(calculated_table(league),hide_index=True,use_container_width=True)
    st.caption("Fallback table calculated from published Division 4 results because the supplied feed was not machine-readable.")

st.header("🥇 Cup Competitions")
for cup,cdf in cups.items():
    st.subheader(cup)
    if cdf.empty:
        st.warning("Could not load this competition.")
        continue
    fx=cdf[cdf.home.map(istarget)|cdf.away.map(istarget)].sort_values("date")
    if fx.empty:
        st.info("No Bishopton FC Black fixture currently found.")
        continue
    for _,r in fx.iterrows():
        opp=r.away if istarget(r.home) else r.home
        home=istarget(r.home)
        score=f"{int(r.hg)}–{int(r.ag)}" if r.status=="FT" else r.status
        st.markdown(f"### {r.date.strftime('%a %d %b %Y')} — {'Home' if home else 'Away'}")
        st.markdown(f"**Bishopton FC Black** vs **{opp}** — **{score}**")
        br,orr=form(all_div,TARGET),form(all_div,opp)
        p=win_chance(br,orr,home)
        c1,c2,c3=st.columns(3)
        c1.metric("Bishopton last 5","".join(br.Result.tolist()) if not br.empty else "—")
        c2.metric("Opponent last 5","".join(orr.Result.tolist()) if not orr.empty else "—")
        c3.metric("Estimated Bishopton win chance",f"{p:.0%}" if p is not None else "N/A")
        with st.expander("Opponent form guide"):
            if orr.empty: st.warning("No completed results found for this opponent in PJDYFL Divisions 1–4.")
            else: st.dataframe(orr[["date","opponent","GF","GA","Result","competition"]].assign(date=lambda x:x.date.dt.strftime("%d/%m/%Y")),hide_index=True,use_container_width=True)
            st.caption("Cup opponents are searched across 2014 Divisions 1–4. Cross-division estimates are lower confidence.")
        st.divider()

st.caption("PJDYFL is the data source. This app is intended as a coaching/fan analytics tool and makes no guarantee about match outcomes.")
