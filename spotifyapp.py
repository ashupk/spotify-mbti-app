# -*- coding: utf-8 -*-
"""
Spotify-Based Personality Profiler – MoodScale (MBTI + OCEAN)

Streamlit app that connects to a user’s Spotify account, predicts an MBTI type
and Big-5 (OCEAN) trait profile from top genres, visualises the Big-5 on a radar
chart, and generates a short personality insight via OpenAI.
"""

# ───────────────────────── Imports ─────────────────────────
import uuid
import pathlib
from collections import Counter

import numpy as np
import matplotlib.pyplot as plt
import openai
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import streamlit as st

# ─────────────────── Secrets (set in Streamlit Cloud) ───────────────────
SPOTIPY_CLIENT_ID     = st.secrets["SPOTIPY_CLIENT_ID"]
SPOTIPY_CLIENT_SECRET = st.secrets["SPOTIPY_CLIENT_SECRET"]
SPOTIPY_REDIRECT_URI  = st.secrets["SPOTIPY_REDIRECT_URI"]
openai.api_key        = st.secrets["OPENAI_API_KEY"]

# ─────────────────────── UI & page config ───────────────────────
st.set_page_config(page_title="Spotify Personality Profiler", layout="centered")
st.title("🎧 Spotify-Based Personality Profiler")
st.markdown(
    "Link your Spotify account to reveal an **MBTI** prediction and a Big-5 "
    "(**OCEAN**) snapshot based on your listening habits."
)

# ─────────────────────── Logout helper ───────────────────────
if st.button("🔓 Logout & Clear Session"):
    if "sid" in st.session_state:
        cache = pathlib.Path(f".cache-{st.session_state['sid']}")
        if cache.exists():
            cache.unlink()
    st.session_state.clear()
    st.success("Logged out. Please reload the app.")
    st.stop()

# ─────────── Per-browser session cache isolation ───────────
if "sid" not in st.session_state:
    st.session_state["sid"] = str(uuid.uuid4())
CACHE_PATH = f".cache-{st.session_state['sid']}"

# ───────────────────── Spotify OAuth ─────────────────────
auth_manager = SpotifyOAuth(
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET,
    redirect_uri=SPOTIPY_REDIRECT_URI,
    scope="user-read-recently-played user-top-read",
    cache_path=CACHE_PATH,
    show_dialog=False,
)

if auth_manager.get_cached_token() is None:
    auth_url = auth_manager.get_authorize_url()
    st.markdown(f"[👉 Connect to Spotify]({auth_url})", unsafe_allow_html=True)
    st.stop()

# ───────────────────── Spotify client ─────────────────────
sp = spotipy.Spotify(auth_manager=auth_manager)
profile = sp.current_user()

# ─────────────────── Helper: MBTI heuristic ───────────────────
def mbti_from_genres(genres: list[str]) -> str:
    if not genres:
        return "Unknown"
    t = {k: 0 for k in "IENS TFJP".replace(" ", "")}
    for g in genres:
        g = g.lower()
        if g in ["indie", "folk", "ambient", "lo-fi"]:
            t["I"] += 1; t["N"] += 1; t["F"] += 1; t["P"] += 1
        elif g in ["pop", "dance pop", "electropop", "k-pop"]:
            t["E"] += 1; t["S"] += 1; t["F"] += 1; t["J"] += 1
        elif g in ["hip hop", "rap", "trap"]:
            t["E"] += 1; t["S"] += 1; t["T"] += 1; t["P"] += 1
        elif g in ["classical", "jazz", "instrumental"]:
            t["I"] += 1; t["N"] += 1; t["T"] += 1; t["J"] += 1
        elif g in ["rock", "metal", "punk"]:
            t["E"] += 1; t["S"] += 1; t["T"] += 1; t["P"] += 1
        elif g in ["r&b", "soul"]:
            t["I"] += 1; t["F"] += 1; t["J"] += 1
        elif g in ["alternative"]:
            t["I"] += 1; t["N"] += 1; t["T"] += 1; t["P"] += 1
    return (
        ("I" if t["I"] >= t["E"] else "E") +
        ("N" if t["N"] >= t["S"] else "S") +
        ("T" if t["T"] >= t["F"] else "F") +
        ("J" if t["J"] >= t["P"] else "P")
    )

# ───────────────── Genre → OCEAN weight table ─────────────────
OCEAN_WEIGHTS = {
    "indie":(4,1,2,2,1), "lo-fi":(4,1,1,2,1), "classical":(5,4,1,3,1), "jazz":(5,3,2,3,1),
    "alt rock":(4,2,3,2,2), "rock":(3,2,4,2,2), "metal":(2,2,4,1,3), "hip hop":(2,2,4,2,2),
    "trap":(2,1,4,2,3), "pop":(3,3,4,3,2), "dance pop":(2,3,5,3,1), "edm":(3,2,5,2,1),
    "r&b":(3,2,3,4,2), "soul":(4,2,3,4,1), "folk":(4,2,2,4,1), "ambient":(4,1,1,3,1),
    "punk":(2,2,4,1,3), "electropop":(3,3,5,3,1), "k-pop":(3,3,5,3,2)
}

def ocean_from_genres(genres: list[str]) -> np.ndarray:
    totals = np.zeros(5); hits = 0
    for g in genres:
        w = OCEAN_WEIGHTS.get(g.lower())
        if w:
            totals += np.array(w); hits += 1
    if hits == 0:
        return np.array([50]*5)
    means = totals / hits                 # 1-5
    return np.interp(means, (1,5), (20,80)).round(1)

# ─────────────── Radar-plot for OCEAN ───────────────
def radar_chart(scores: np.ndarray):
    labels = ["Openness", "Conscientious.", "Extraversion",
              "Agreeableness", "Neuroticism"]
    angles = np.linspace(0, 2*np.pi, len(labels), endpoint=False)
    values = np.concatenate((scores, [scores[0]]))
    angs   = np.concatenate((angles, [angles[0]]))

    fig, ax = plt.subplots(figsize=(4,4), subplot_kw=dict(polar=True))
    ax.plot(angs, values, linewidth=2)
    ax.fill(angs, values, alpha=0.25)
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylim(0,100)
    ax.set_title("Big-5 Personality Radar", pad=18)
    st.pyplot(fig)

# ─────────────── Insight via OpenAI ───────────────
def generate_insight(mbti: str, ocean: np.ndarray, tracks: list[str]) -> str:
    track_block = "\n".join(f"{i+1}. {t}" for i, t in enumerate(tracks[:20]))
    ocean_txt   = ", ".join(
        f"{n} {v}" for n, v in zip(["O","C","E","A","N"], ocean)
    )
    prompt = (
        f"MBTI: {mbti}. Big-5: {ocean_txt}.\n"
        f"Recent tracks:\n{track_block}\n"
        "Write 8 lines, each beginning with 'You are someone who…', "
        "summarising the person's personality."
    )
    rsp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":"You are a music-savvy personality profiler."},
            {"role":"user","content":prompt}
        ]
    )
    return rsp.choices[0].message["content"].strip()

# ─────────────────────────── Data fetch & display ───────────────────────────
name = profile.get("display_name", "there")
st.write("👤 Logged in as:", name)

# Top genres
artists     = sp.current_user_top_artists(limit=20, time_range="medium_term")
genres_flat = [g for a in artists["items"] for g in a["genres"]]
top_genres  = [g for g,_ in Counter(genres_flat).most_common(10)]
st.write("🎵 Top genres:", top_genres or "No genre data")

# Recent tracks
recent      = sp.current_user_recently_played(limit=50)
track_list  = [
    f"{item['track']['name']} – {item['track']['artists'][0]['name']}"
    for item in recent["items"]
]

# Personality outputs
mbti  = mbti_from_genres(top_genres)
ocean = ocean_from_genres(top_genres)  # np.ndarray of 5 scores

if mbti != "Unknown":
    st.subheader(f"🧠 MBTI Prediction: **{mbti}**")
else:
    st.warning("Not enough genre data to determine MBTI.")

st.subheader("🌊 Big-5 (OCEAN) Profile")
radar_chart(ocean)

with st.spinner("🔍 Generating personality insight..."):
    insight = generate_insight(mbti, ocean, track_list)

st.subheader("📖 Personality Insight")
st.write(insight)
