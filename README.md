# Bishopton FC Black 2014 — Fixture & Form Guide

Streamlit app using live PJDYFL data.

### Features
- Division 4 fixtures for Bishopton FC Black 2014
- Last-five form guide under each fixture
- Rough Bishopton win percentage
- Division 4 league table using feed 1104 when readable, with a calculated fallback
- Scottish Cup 2014 and League Cup 2014 sections
- Cup opponent form from PJDYFL 2014 Divisions 1–4
- No API key required

### Streamlit deployment
Upload `app.py`, `requirements.txt` and `README.md` to GitHub, then create a Streamlit Community Cloud app with `app.py` as the main file.

The PJDYFL site is cached for 15 minutes. Use the Refresh button to force a reload.
