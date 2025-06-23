# -*- coding: utf-8 -*-
"""
Spotify-Based Personality Profiler - MoodScale
Fully Streamlit-compatible | OpenAI SDK v1.x safe
"""

import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from collections import Counter
import os
from openai import OpenAI

# --- Load secrets from Streamlit Cloud or local .toml ---
SPOTIPY_CLIENT_ID = st.secrets["SPOTIPY_CLIENT_ID"]
SPOTIPY_CLIENT_SECRET = st.secrets["SPOTIPY_CLIENT_SECRET"]
SPOTIPY_REDIRECT_URI = st.secrets["SPOTIPY_REDIRECT_URI"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

# --- Set API key as environment variable (for OpenAI client compatibility) ---
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# --- Streamlit page config ---
st.set_page_config(page_title="Spotify Personality Profiler", layout="centered")
st.title("🎧 Spotify-Based Personality Profiler")
st.markdown("Connect your Spotify to receive a personality assessment based on your music preferences.")

# --- Spotify OAuth setup ---
sp_oauth = SpotifyOAuth(
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET,
    redirect_uri=SPOTIPY_REDIRECT_URI,
    scope='user-top-read user-read-recently-played',
    show_dialog=True,
    cache_path=".cache"
)

# --- Initialize token_info ---
token_info = None

# --- Handle Spotify redirect ---
if "token_info" not in st.session_state:
    query_params = st.query_params
    if "code" in query_params:
        try:
            code = query_params["code"]
            token_info = sp_oauth.get_access_token(code)
            st.session_state.token_info = token_info
            st.success("Spotify connected! Generating your profile...")
        except spotipy.oauth2.SpotifyOauthError as e:
            st.error("Spotify authorization failed. Please try again.")
            st.stop()
else:
    token_info = st.session_state.token_info

# --- MBTI prediction from genres ---
def mbti_from_genres(genres):
    traits = {'I': 0, 'E': 0, 'N': 0, 'S': 0, 'T': 0, 'F': 0, 'J': 0, 'P': 0}
    for genre in genres:
        genre = genre.lower()
        if genre in ['indie', 'folk', 'ambient', 'lo-fi']:
            traits['I'] += 1; traits['N'] += 1; traits['F'] += 1; traits['P'] += 1
        elif genre in ['pop', 'dance pop', 'electropop', 'k-pop']:
            traits['E'] += 1; traits['S'] += 1; traits['F'] += 1; traits['J'] += 1
        elif genre in ['hip hop', 'rap', 'trap']:
            traits['E'] += 1; traits['S'] += 1; traits['T'] += 1; traits['P'] += 1
        elif genre in ['classical', 'jazz', 'instrumental']:
            traits['I'] += 1; traits['N'] += 1; traits['T'] += 1; traits['J'] += 1
        elif genre in ['rock', 'metal', 'punk']:
            traits['E'] += 1; traits['S'] += 1; traits['T'] += 1; traits['P'] += 1
        elif genre in ['r&b', 'soul']:
            traits['I'] += 1; traits['F'] += 1; traits['J'] += 1
        elif genre in ['alternative']:
            traits['I'] += 1; traits['N'] += 1; traits['T'] += 1; traits['P'] += 1
    return (
        ('I' if traits['I'] >= traits['E'] else 'E') +
        ('N' if traits['N'] >= traits['S'] else 'S') +
        ('T' if traits['T'] >= traits['F'] else 'F') +
        ('J' if traits['J'] >= traits['P'] else 'P')
    )

# --- OpenAI-based personality insight ---
def generate_personality_insight(mbti, track_list):
    client = OpenAI()
    track_info = "\n".join([f"{i+1}. {track}" for i, track in enumerate(track_list)])
    prompt = f"""
You are a psychologist with expertise in personality and music psychology.
A person has the MBTI type: {mbti}
These are the last 50 tracks they listened to:
{track_info}

Based on this, write a 6-8 line personality insight using "You are someone who..." style.
"""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a personality profiler skilled in interpreting music preferences."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()

# --- Main logic ---
if token_info:
    sp = spotipy.Spotify(auth=token_info["access_token"])
    profile = sp.current_user()
    display_name = profile.get("display_name", "there")

    top_artists = sp.current_user_top_artists(limit=20, time_range="medium_term")
    genres = [genre for artist in top_artists["items"] for genre in artist["genres"]]
    top_genres = [genre for genre, _ in Counter(genres).most_common(10)]

    recent_tracks = sp.current_user_recently_played(limit=50)
    track_list = [f"{item['track']['name']} – {item['track']['artists'][0]['name']}" for item in recent_tracks["items"]]

    mbti = mbti_from_genres(top_genres)

    st.subheader(f"Hi {display_name}, your predicted MBTI type is: 🧠 {mbti}")
    st.subheader("📖 Personality Insight")

    with st.spinner("Analyzing your music taste..."):
        insight = generate_personality_insight(mbti, track_list)

    st.write(insight)

else:
    auth_url = sp_oauth.get_authorize_url()
    st.markdown(f"[Connect to Spotify]({auth_url})", unsafe_allow_html=True)
