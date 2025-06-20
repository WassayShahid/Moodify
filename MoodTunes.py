import cv2
import os
import re
import json
import time
import random
import requests
from dotenv import load_dotenv
from deepface import DeepFace
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials


load_dotenv(dotenv_path="./keys.env")

CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=CLIENT_ID, client_secret=CLIENT_SECRET))

emotion_tracks = {
    "happy": [], "sad": [], "angry": [],
    "energetic": [], "calm": [], "neutral": []
}

deepface_to_app_emotion_map = {
    "happy": "happy", "sad": "sad", "angry": "angry", "neutral": "neutral",
    "fear": "angry", "surprise": "energetic", "disgust": "angry"
}


def capture_frame():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Unable to open webcam.")
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise RuntimeError("Failed to capture frame.")
    return frame

def analyze_frame(frame):
    try:
        results = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False, silent=True)
        if isinstance(results, list) and results:
            detected = results[0]['dominant_emotion'].lower()
        else:
            detected = "neutral"
        return deepface_to_app_emotion_map.get(detected, "neutral")
    except Exception as e:
        print(f"Emotion analysis error: {e}")
        return "neutral"


def extract_playlist_id(url):
    match = re.search(r'playlist/([\w\d]+)', url)
    if match:
        return match.group(1)
    raise ValueError("Invalid Spotify playlist URL.")

def get_tracks_from_playlist_spotify(playlist_id):
    tracks = []
    results = sp.playlist_items(playlist_id, fields="items(track(id,name,artists(name))),next")
    while results:
        for item in results['items']:
            t = item.get('track')
            if t:
                tracks.append({"spotify_id": t['id'], "name": t['name'], "artist": t['artists'][0]['name']})
        results = sp.next(results) if results['next'] else None
        time.sleep(0.1)
    return tracks


def get_lastfm_tags(track_name, artist_name):
    url = f"http://ws.audioscrobbler.com/2.0/"
    params = {
        "method": "track.gettoptags",
        "artist": artist_name,
        "track": track_name,
        "api_key": LASTFM_API_KEY,
        "format": "json"
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        tags = [tag['name'].lower() for tag in data.get('toptags', {}).get('tag', [])]
        return tags
    except Exception as e:
        print(f"Failed to fetch Last.fm tags for {track_name} by {artist_name}: {e}")
        return []

def classify_emotion_from_tags(tags):
    tag_map = {
        "happy": ["happy", "fun", "upbeat", "joy", "sunshine", "cheerful", "feel good"],
        "sad": ["sad", "melancholy", "depressing", "heartbreak", "emotional", "lonely"],
        "angry": ["angry", "aggressive", "rage", "dark", "metalcore", "hardcore"],
        "energetic": ["energetic", "party", "dance", "fast", "hype", "electronic"],
        "calm": ["calm", "chill", "relaxing", "ambient", "soft", "soothing"]
    }
    tag_set = set(tags)
    scores = {emotion: len(tag_set & set(match_tags)) for emotion, match_tags in tag_map.items()}
    max_emotion = max(scores.items(), key=lambda x: x[1], default=("neutral", 0))
    return max_emotion[0] if max_emotion[1] > 0 else "neutral"


def process_playlist(playlist_url):
    global emotion_tracks
    emotion_tracks = {k: [] for k in emotion_tracks}
    playlist_id = extract_playlist_id(playlist_url)
    tracks = get_tracks_from_playlist_spotify(playlist_id)
    for t in tracks:
        tags = get_lastfm_tags(t['name'], t['artist'])
        emotion = classify_emotion_from_tags(tags)
        emotion_tracks[emotion].append(f"{t['name']} by {t['artist']}")
        print(f"{t['name']} by {t['artist']} → {emotion}")
    return emotion_tracks

def recommend_tracks(emotion, emotion_tracks_dict):
    return random.sample(emotion_tracks_dict.get(emotion, []), min(3, len(emotion_tracks_dict.get(emotion, []))))
