import cv2
from deepface import DeepFace
import re
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os
import random
from dotenv import load_dotenv

# Load environment variables
load_dotenv('./keys.env')
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')

sp = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET
))

# Spotify & Emotion Setup
emotion_tracks = { "happy": [], "sad": [], "angry": [], "neutral": [], "fear": [], "surprised": [], "disgust": [] }

def extract_playlist_id(playlist_url):
    match = re.search(r'playlist/([\w\d]+)', playlist_url)
    return match.group(1) if match else None

def get_tracks_from_playlist(playlist_id):
    tracks = []
    results = sp.playlist_items(playlist_id)
    while results:
        tracks.extend(results['items'])
        results = sp.next(results) if results['next'] else None
    return tracks

def get_audio_features(track_ids):
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
    local_tracks = {key: [] for key in emotion_tracks}
    try:
        playlist_id = extract_playlist_id(playlist_url)
        if not playlist_id:
            raise ValueError("Invalid playlist URL.")
        tracks = get_tracks_from_playlist(playlist_id)
        track_ids = [track['track']['id'] for track in tracks if track['track']]
        audio_features = get_audio_features(track_ids)
        for feature, track in zip(audio_features, tracks):
            if feature:
                emotion = calculate_emotion(feature)
                track_name = track['track']['name']
                artist_name = track['track']['artists'][0]['name']
                local_tracks[emotion].append(f"{track_name} by {artist_name}")
    except Exception as e:
        print("Error:", e)
    return local_tracks

def capture_frame():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Webcam not accessible")
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise RuntimeError("Failed to capture frame from webcam")
    return frame

def analyze_frame(frame):
    try:
        result = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
        return result[0]['dominant_emotion'] if isinstance(result, list) else result['dominant_emotion']
    except Exception as e:
        print("Emotion analysis failed:", e)
        return "neutral"

def recommend_tracks(emotion, track_dict):
    return random.sample(track_dict.get(emotion, []), min(5, len(track_dict.get(emotion, []))))
