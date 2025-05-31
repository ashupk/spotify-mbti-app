# -*- coding: utf-8 -*-
"""
Created on Sun Jun  1 02:40:04 2025
Updated for Streamlit Cloud Deployment
@author: MoodScale_Betav1.3
"""

import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from collections import Counter
from openai import OpenAI

# --- CONFIGURATION ---
SPOTIPY_CLIENT_ID = st.secrets["SPOTIPY_CLIENT_ID"]
SPOTIPY_CLIENT_SECRET = st.secrets["SPOTIPY_CLIENT_SECRET"]
SPOTIPY_REDIRECT_URI = st.secrets["SPOTIPY_REDIRECT_URI"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

# --- Streamlit Page Setup ---
st.set_page_config(page_title="Spotify Personality Profiler - MoodScale", layout="centered")
st.title("\U0001F3A7 Spotify-Based Personality Profiler - MoodScale")
st.write("Connect your Spotify with MoodScale to receive a personality assessment based on your music preferences.")

# --- Spotify OAuth Setup ---
sp_oauth = SpotifyOAuth(
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET,
    redirect_uri=SPOTIPY_REDIRECT_URI,
    scope='user-top-read user-read-recently-played'
)

# --- Authorization Flow ---
token_info = None
query_params = st.query_params
code = query_params.get("code", [None])[0]

if code:
    try:
        token_info = sp_oauth.get_access_token(code)
        st.success("Spotify connected! Generating your profile...")
    except Exception as e:
        st.error("Spotify authorization failed. Please try again.")
        st.stop()

# --- Helper Functions ---
def mbti_from_genres(genres):
    mbti_traits = {'I': 0, 'E': 0, 'N': 0, 'S': 0, 'T': 0, 'F': 0, 'J': 0, 'P': 0}
    for genre in genres:
        genre = genre.lower()
        if genre in ['indie', 'folk', 'ambient', 'lo-fi']:
            mbti_traits['I'] += 1; mbti_traits['N'] += 1; mbti_traits['F'] += 1; mbti_traits['P'] += 1
        elif genre in ['pop', 'dance pop', 'electropop', 'k-pop']:
            mbti_traits['E'] += 1; mbti_traits['S'] += 1; mbti_traits['F'] += 1; mbti_traits['J'] += 1
        elif genre in ['hip hop', 'rap', 'trap']:
            mbti_traits['E'] += 1; mbti_traits['S'] += 1; mbti_traits['T'] += 1; mbti_traits['P'] += 1
        elif genre in ['classical', 'jazz', 'instrumental']:
            mbti_traits['I'] += 1; mbti_traits['N'] += 1; mbti_traits['T'] += 1; mbti_traits['J'] += 1
        elif genre in ['rock', 'metal', 'punk']:
            mbti_traits['E'] += 1; mbti_traits['S'] += 1; mbti_traits['T'] += 1; mbti_traits['P'] += 1
        elif genre in ['r&b', 'soul']:
            mbti_traits['I'] += 1; mbti_traits['F'] += 1; mbti_traits['J'] += 1
        elif genre in ['alternative']:
            mbti_traits['I'] += 1; mbti_traits['N'] += 1; mbti_traits['T'] += 1; mbti_traits['P'] += 1

    mbti = ''
    mbti += 'I' if mbti_traits['I'] >= mbti_traits['E'] else 'E'
    mbti += 'N' if mbti_traits['N'] >= mbti_traits['S'] else 'S'
    mbti += 'T' if mbti_traits['T'] >= mbti_traits['F'] else 'F'
    mbti += 'J' if mbti_traits['J'] >= mbti_traits['P'] else 'P'
    return mbti

def generate_personality_insight(mbti_type, track_list):
    client = OpenAI(api_key=OPENAI_API_KEY)
    track_info = '\n'.join([f"{i+1}. {track}" for i, track in enumerate(track_list)])
    prompt = f"""
You are a psychologist with expertise in personality and music psychology.
A person has the Myers-Briggs personality type: {mbti_type}
Here are the last 50 songs this person has listened to:
{track_info}
Based on the MBTI type and the songs, write a 6-8 line personality assessment. Focus on emotional depth, introspective qualities, thinking style, and social preferences. Write it in second person ("You are someone who...").
"""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a psychological profiler skilled in behavioral and music-based personality assessment."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()

# --- Main App Logic ---
if token_info:
    sp = spotipy.Spotify(auth=token_info['access_token'])
    profile = sp.current_user()
    display_name = profile.get("display_name", "there")

    # Get top genres
    top_artists = sp.current_user_top_artists(limit=20, time_range='medium_term')
    all_genres = []
    for artist in top_artists['items']:
        all_genres.extend(artist['genres'])
    genre_counts = Counter(all_genres)
    top_genres = [genre for genre, count in genre_counts.most_common(10)]
    mbti = mbti_from_genres(top_genres)

    # Get 50 tracks
    results = sp.current_user_recently_played(limit=50)
    track_list = [f"{item['track']['name']} – {item['track']['artists'][0]['name']}" for item in results['items']]

    st.subheader(f"Hi {display_name}, your predicted MBTI type is: \U0001F9E0 {mbti}")
    st.subheader("\U0001F4D6 Personality Insight")
    with st.spinner("Analyzing your taste and personality..."):
        insight = generate_personality_insight(mbti, track_list)
    st.write(insight)

else:
    auth_url = sp_oauth.get_authorize_url()
    st.markdown(f"[Connect to Spotify]({auth_url})", unsafe_allow_html=True)
