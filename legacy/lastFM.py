import cv2
from deepface import DeepFace
import re
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import time
import os
import random
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv('./keys.env')
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
LASTFM_API_KEY = os.getenv('LASTFM_API_KEY')

# Spotify setup
client_credentials_manager = SpotifyClientCredentials(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

# Emotion categories dictionary
emotion_tracks = {
    "happy": [],
    "sad": [],
    "angry": [],
    "neutral": [],
    "fear": [],
    "surprised": [],
    "disgust": []
}

# Tag to emotion mapping
tag_to_emotion = {
    'happy': 'happy', 'fun': 'happy', 'uplifting': 'happy', 'energetic': 'happy', 'joy': 'happy', 'pop': 'happy',
    'sad': 'sad', 'melancholic': 'sad', 'depressing': 'sad', 'emotional': 'sad', 'emo': 'sad',
    'angry': 'angry', 'aggressive': 'angry', 'metal': 'angry', 'rage': 'angry',
    'calm': 'neutral', 'chill': 'neutral', 'ambient': 'neutral', 'soft': 'neutral', 'relaxing': 'neutral',
    'romantic': 'happy', 'love': 'happy',
    'dark': 'fear', 'gothic': 'fear',
    'epic': 'surprised', 'intense': 'surprised', 'powerful': 'surprised',
    'weird': 'disgust', 'strange': 'disgust'
}

# Last.fm top tags fetch
def get_lastfm_tags(track, artist):
    try:
        url = "http://ws.audioscrobbler.com/2.0/"
        params = {
            'method': 'track.gettoptags',
            'track': track,
            'artist': artist,
            'api_key': LASTFM_API_KEY,
            'format': 'json'
        }
        response = requests.get(url, params=params)
        data = response.json()
        return [tag['name'].lower() for tag in data.get('toptags', {}).get('tag', [])]
    except:
        return []

# Tag-based emotion inference
def infer_emotion_from_tags(tags):
    scores = {emotion: 0 for emotion in emotion_tracks}
    for tag in tags:
        if tag in tag_to_emotion:
            scores[tag_to_emotion[tag]] += 1
    return max(scores, key=scores.get) if any(scores.values()) else "neutral"

# Extract playlist ID
def extract_playlist_id(playlist_url):
    match = re.search(r'playlist/([\w\d]+)', playlist_url)
    if match:
        return match.group(1)
    raise ValueError("Invalid playlist URL.")

# Get all tracks from playlist
def get_tracks_from_playlist(playlist_id):
    tracks = []
    results = sp.playlist_items(playlist_id)
    while results:
        tracks.extend(results['items'])
        results = sp.next(results) if results['next'] else None
    return tracks

# Categorize tracks using Last.fm
def add_tracks_to_emotion_dict(playlist_url):
    try:
        playlist_id = extract_playlist_id(playlist_url)
        tracks = get_tracks_from_playlist(playlist_id)
        print("Analyzing playlist...")
        for item in tracks:
            track = item['track']
            if not track: continue
            track_name = track['name']
            artist_name = track['artists'][0]['name']
            print(f"Getting tags for: {track_name} by {artist_name}")
            tags = get_lastfm_tags(track_name, artist_name)
            emotion = infer_emotion_from_tags(tags)
            emotion_tracks[emotion].append(f"{track_name} by {artist_name}")
            print(f"→ {track_name} → {emotion}")
        print("\n🎧 Tracks categorized by emotion:")
        for emotion, tracks in emotion_tracks.items():
            print(f"{emotion}: {len(tracks)} tracks")
    except Exception as e:
        print(f"Error: {e}")

# Main entry
playlist_url = input("Enter your Spotify playlist URL: ")
add_tracks_to_emotion_dict(playlist_url)

# Webcam setup for real-time emotion detection
cap = cv2.VideoCapture(0)
last_emotion = None
last_emotion_time = 0

while True:
    ret, frame = cap.read()
    if not ret:
        print("Failed to capture image")
        break

    try:
        # Detect face emotion
        results = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
        emotion = results[0]['dominant_emotion'] if isinstance(results, list) else results['dominant_emotion']

        # Show emotion on screen
        cv2.putText(frame, f'Emotion: {emotion}', (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)

        current_time = time.time()
        if emotion != last_emotion or (current_time - last_emotion_time >= 30):
            last_emotion = emotion
            last_emotion_time = current_time

            # Recommend tracks
            if emotion in emotion_tracks and emotion_tracks[emotion]:
                sample = random.sample(emotion_tracks[emotion], min(5, len(emotion_tracks[emotion])))
                print(f"\n🎶 Recommended songs for {emotion}:")
                for song in sample:
                    print("•", song)
            else:
                print(f"\n😕 No tracks found for emotion: {emotion}")

    except Exception as e:
        print("Error analyzing frame:", e)

    cv2.imshow('Emotion Detector', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
