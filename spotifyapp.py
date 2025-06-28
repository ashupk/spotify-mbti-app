# -*- coding: utf-8 -*-
"""
Spotify‑Based Personality Profiler ‑ MoodScale (MBTI + OCEAN)
This Streamlit app connects to a user’s Spotify account, retrieves top genres and
recent tracks, predicts both MBTI and Big‑5 (OCEAN) traits, visualises the Big‑5
as a radar chart, and produces an AI‑generated personality insight.
"""

import os
import uuid
import pathlib
from collections import Counter

import numpy as np
import matplotlib.pyplot as plt
import openai
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import streamlit as st

# ───────────────────────────  Secrets & Keys  ────────────────────────────
SPOTIPY_CLIENT_ID = st.secrets["SPOTIPY_CLIENT_ID"]
SPOTIPY_CLIENT_SECRET = st.secrets["SPOTIPY_CLIENT_SECRET"]
SPOTIPY_REDIRECT_URI = st.secrets["SPOTIPY_REDIRECT_URI"]
openai.api_key = st.secrets["OPENAI_API_KEY"]

# ────────────────────────────  Page Set‑up  ─────────────────────────────
st.set_page_config(page_title="Spotify Personality Profiler", layout="centered")
st.title("🎧 Spotify‑Based Personality Profiler")
st.markdown(
    "Link your Spotify account to reveal an **MBTI** prediction *and* a Big‑5 "
    "(**OCEAN**) snapshot based on your listening habits."
)

# ────────────────────────────  Logout Button  ───────────────────────────
if st.button("🔓 Logout & Clear Session"):
    if "sid" in st.session_state:
        cache = pathlib.Path(f".cache-{st.session_state['sid']}")
        if cache.exists():
            cache.unlink()
    st.session_state.clear()
    st.success("Logged out. Please reload the app.")
    st.stop()

# ───────────────────────  Session‑scoped Cache File  ─────────────────────
if "sid" not in st.session_state:
    st.session_state["sid"] = str(uuid.uuid4())
cache_path = f".cache-{st.session_state['sid']}"

# ───────────────────────────  Spotify OAuth  ────────────────────────────
auth_manager = SpotifyOAuth(
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET,
    redirect_uri=SPOTIPY_REDIRECT_URI,
    scope="user-top-read user-read-recently-played",
    cache_path=cache_path,
    show_dialog=False,
)

try:
    sp = spotipy.Spotify(auth_manager=auth_manager)
except spotipy.oauth2.SpotifyOauthError:
    st.error("Spotify authorisation failed. Please try again.")
    st.stop()

# ──────────────────────────  Helper Functions  ──────────────────────────

def mbti_from_genres(genres):
    """Very light‑weight heuristic to map genres → MBTI."""
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

# ─────────────  Genre → OCEAN weight matrix (1 low → 5 high)  ────────────
OCEAN_WEIGHTS = {
    # Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism
    "indie"       : (4, 1, 2, 2, 1),
    "lo-fi"       : (4, 1, 1, 2, 1),
    "classical"   : (5, 4, 1, 3, 1),
    "jazz"        : (5, 3, 2, 3, 1),
    "alt rock"    : (4, 2, 3, 2, 2),
    "rock"        : (3, 2, 4, 2, 2),
    "metal"       : (2, 2, 4, 1, 3),
    "hip hop"     : (2, 2, 4, 2, 2),
    "trap"        : (2, 1, 4, 2, 3),
    "pop"         : (3, 3, 4, 3, 2),
    "dance pop"   : (2, 3, 5, 3, 1),
    "edm"         : (3, 2, 5, 2, 1),
    "r&b"         : (3, 2, 3, 4, 2),
    "soul"        : (4, 2, 3, 4, 1),
    "folk"        : (4, 2, 2, 4, 1),
    "ambient"     : (4, 1, 1, 3, 1),
    "punk"        : (2, 2, 4, 1, 3),
    "electropop"  : (3, 3, 5, 3, 1),
    "k-pop"       : (3, 3, 5, 3, 2),
}


def ocean_from_genres(genres):
    """Return 5 scaled Big‑5 scores (0‑100)."""
    trait_totals = np.zeros(5)
    hits = 0
    for g in genres:
        g = g.lower()
        if g in OCEAN_WEIGHTS:
            trait_totals += np.array(OCEAN_WEIGHTS[g])
            hits += 1
    if hits == 0:
        return np.array([50] * 5)
    means = trait_totals / hits  # 1‑5 scale
    return np.interp(means, (1, 5), (20, 80)).round(1)


def radar_chart(scores):
    labels = ["Openness", "Conscientious.", "Extraversion",
              "Agreeableness", "Neuroticism"]
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False)
    values = np.concatenate((scores, [scores[0]]))
    angles = np.concatenate((angles, [angles[0]]))

    fig, ax = plt.subplots(figsize=(4, 4), subplot_kw=dict(polar=True))
    ax.plot(angles, values, linewidth=2)
    ax.fill(angles, values, alpha=0.25)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylim(0, 100)
    ax.set_title("Big‑5 Personality Radar", pad=20, fontsize=12)
    st.pyplot(fig)


def generate_personality_insight(mbti, ocean_scores, tracks):
    track_snippet = "\n".join(f"{i+1}. {t}" for i, t in enumerate(tracks[:20]))
    ocean_text = ", ".join([
        f"Openness {ocean_scores[0]}",
        f"Conscientiousness {ocean_scores[1]}",
        f"Extraversion {ocean_scores[2]}",
        f"Agreeableness {ocean_scores[3]}",
        f"Neuroticism {ocean_scores[4]}"
    ])

    prompt = f"""
You are a psychologist with expertise in personality and music psychology.
A person has the MBTI type: {mbti}
Their Big‑5 trait scores are: {ocean_text}
Here are 20 of their recent tracks:
{track_snippet}

Write an 8‑line personality insight using "You are someone who..." style.
"""
    rsp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a music‑savvy personality profiler."},
            {"role": "user", "content": prompt},
        ],
    )
    return rsp.choices[0].message["content"].strip()

# ─────────────────────────────  Main Flow  ──────────────────────────────
try:
    profile = sp.current_user()
except spotipy.exceptions.SpotifyException:
    st.error("Could not fetch profile data. Please reconnect Spotify.")
    st.stop()

name = profile.get("display_name", "there")
st.write("👤 Logged in as:", name)
st.write("🆔 Spotify ID:", profile.get("id"))

# Fetch top genres
artists = sp.current_user_top_artists(limit=20, time_range="medium_term")
raw_genres = [g for a in artists["items"] for g in a["genres"]]
top_genres = [g for g, _ in Counter(raw_genres).most_common(10)]
st.write("🎵 Top genres detected:", top_genres or "No genre data")

# Fetch recent tracks
t_recent = sp.current_user_recently_played(limit=50)
tracks = [f"{i['track']['name']} – {i['track']['artists'][0]['name']}" for i in t_recent["items"]]

# MBTI & OCEAN
mbti = mbti_from_genres(top_genres)
ocean = ocean_from_genres(top_genres)

if mbti != "Unknown":
    st.subheader(f"🧠 MBTI Prediction: **{mbti}**")
else:
    st.warning("Not enough genre data to determine MBTI.")

st.subheader("🌊 Big‑5 (OCEAN) Profile")
radar_chart(ocean)

with st.spinner("🔍 Generating personality insight..."):
    insight = generate_personality_insight(mbti, ocean, tracks)

st.subheader("📖 Personality Insight")
st.write(insight)
