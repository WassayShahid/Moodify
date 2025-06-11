import cv2
from deepface import DeepFace
import re
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os
import time
import random
from dotenv import load_dotenv

# Load credentials
load_dotenv(dotenv_path='./keys.env')

CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')

if not CLIENT_ID or not CLIENT_SECRET:
    raise Exception("Spotify CLIENT_ID or CLIENT_SECRET not found in keys.env")

# Emotion categories
emotion_tracks = {
    "happy": [],
    "sad": [],
    "angry": [],
    "neutral": [],
    "fear": [],
    "surprised": [],
    "disgust": []
}

def load_spotify():
    credentials = SpotifyClientCredentials(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
    return spotipy.Spotify(client_credentials_manager=credentials)

sp = load_spotify()

def extract_playlist_id(playlist_url):
    match = re.search(r'playlist/([\w\d]+)', playlist_url)
    if match:
        return match.group(1)
    raise ValueError("Invalid playlist URL format.")

def get_tracks_from_playlist(playlist_id):
    tracks = []
    results = sp.playlist_items(playlist_id)
    while results:
        tracks.extend(results['items'])
        results = sp.next(results) if results['next'] else None
    return tracks

def get_audio_features_for_tracks(track_ids):
    features = []
    for i in range(0, len(track_ids), 100):
        features.extend(sp.audio_features(track_ids[i:i + 100]))
    return features

def calculate_emotion(features):
    valence = features['valence']
    energy = features['energy']
    danceability = features['danceability']
    acousticness = features['acousticness']
    tempo = features['tempo']
    mode = features['mode']

    if valence > 0.75 and energy > 0.6:
        return "happy"
    elif valence < 0.4 and energy < 0.4:
        return "sad"
    elif energy > 0.8 and valence < 0.5:
        return "angry"
    elif valence < 0.3 and acousticness > 0.5 and mode == 0:
        return "fear"
    elif energy > 0.7 and tempo > 120:
        return "surprised"
    elif valence < 0.4 and danceability < 0.4:
        return "disgust"
    else:
        return "neutral"

def process_playlist(playlist_url):
    global emotion_tracks
    emotion_tracks = {key: [] for key in emotion_tracks}  # reset
    playlist_id = extract_playlist_id(playlist_url)
    tracks = get_tracks_from_playlist(playlist_id)
    track_ids = [track['track']['id'] for track in tracks if track['track']]
    audio_features = get_audio_features_for_tracks(track_ids)

    for feature, track in zip(audio_features, tracks):
        if feature:
            emotion = calculate_emotion(feature)
            name = track['track']['name']
            artist = track['track']['artists'][0]['name']
            emotion_tracks[emotion].append(f"{name} by {artist}")
    return emotion_tracks

def capture_frame():
    cap = cv2.VideoCapture(0)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise Exception("Failed to capture frame from webcam.")
    return frame

def analyze_frame(frame):
    try:
        results = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
        return results[0]['dominant_emotion'] if isinstance(results, list) else results['dominant_emotion']
    except Exception as e:
        raise Exception(f"Emotion detection error: {e}")

def recommend_tracks(emotion, emotion_tracks):
    if emotion in emotion_tracks and emotion_tracks[emotion]:
        return random.sample(emotion_tracks[emotion], min(5, len(emotion_tracks[emotion])))
    else:
        return [f"No tracks found for emotion: {emotion}"]
