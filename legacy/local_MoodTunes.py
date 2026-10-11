import os
import re
import time
import random
import cv2
from dotenv import load_dotenv
from deepface import DeepFace
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import lyricsgenius
from transformers import pipeline

# Load environment variables
env_path = './keys.env'
load_dotenv(dotenv_path=env_path)

# API credentials
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
GENIUS_ACCESS_TOKEN = os.getenv('GENIUS_ACCESS_TOKEN')

# Initialize Spotify and Genius clients
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=CLIENT_ID, client_secret=CLIENT_SECRET))
genius = lyricsgenius.Genius(GENIUS_ACCESS_TOKEN, skip_non_songs=True, excluded_terms=["(Remix)", "(Live)"])
genius.timeout = 15

# Load Hugging Face sentiment analysis model
sentiment_model = pipeline("sentiment-analysis")

# Emotion dictionary
emotion_tracks = {
    "happy": [],
    "sad": [],
    "angry": [],
    "neutral": [],
    "fear": [],
    "surprised": [],
    "disgust": []
}

# Extract Spotify playlist ID
def extract_playlist_id(playlist_url):
    match = re.search(r'playlist/([\w\d]+)', playlist_url)
    if match:
        return match.group(1)
    raise ValueError("Invalid playlist URL.")

# Get all tracks from a playlist
def get_tracks_from_playlist(playlist_id):
    tracks = []
    results = sp.playlist_items(playlist_id)
    while results:
        tracks.extend(results['items'])
        results = sp.next(results) if results['next'] else None
    return tracks

# Get lyrics from Genius
def get_lyrics(title, artist):
    try:
        song = genius.search_song(title, artist)
        return song.lyrics if song else None
    except Exception:
        return None

# Analyze sentiment with Hugging Face and map to emotion
def analyze_sentiment(lyrics):
    if not lyrics:
        return "neutral"
    try:
        lyrics_short = lyrics[:1000]  # Truncate to avoid token limit
        result = sentiment_model(lyrics_short)[0]
        label = result['label']
        score = result['score']
        
        if label == "POSITIVE" and score > 0.8:
            return "happy"
        elif label == "NEGATIVE" and score > 0.8:
            return "sad"
        elif label == "NEGATIVE" and score < 0.6:
            return "angry"
        else:
            return "neutral"
    except Exception as e:
        print(f"Sentiment error: {e}")
        return "neutral"

# Categorize tracks into emotion dictionary
def add_tracks_to_emotion_dict(playlist_url):
    try:
        playlist_id = extract_playlist_id(playlist_url)
        tracks = get_tracks_from_playlist(playlist_id)

        print("Fetching lyrics and analyzing sentiment...\n")
        for track in tracks:
            if not track['track']: continue
            track_name = track['track']['name']
            artist_name = track['track']['artists'][0]['name']
            print(f"Searching for \"{track_name}\" by {artist_name}...")
            lyrics = get_lyrics(track_name, artist_name)
            emotion = analyze_sentiment(lyrics)
            emotion_tracks[emotion].append(f"{track_name} by {artist_name}")
            print(f"{track_name} by {artist_name} → {emotion}")

        print("\nTracks categorized by emotion:")
        for emotion, songs in emotion_tracks.items():
            print(f"{emotion}: {len(songs)} tracks")

    except Exception as e:
        print(f"Error processing playlist: {e}")

# --- MAIN EXECUTION ---

# Input playlist
playlist_url = input("Enter your Spotify playlist URL: ")
add_tracks_to_emotion_dict(playlist_url)

# Webcam + DeepFace emotion detection
cap = cv2.VideoCapture(0)
last_emotion = None
last_emotion_time = 0

print("\nStarting webcam for emotion detection... Press 'q' to quit.")

while True:
    ret, frame = cap.read()
    if not ret:
        print("Failed to capture image.")
        break

    try:
        results = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
        emotion = results[0]['dominant_emotion'] if isinstance(results, list) else results['dominant_emotion']
        cv2.putText(frame, f'Emotion: {emotion}', (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)

        current_time = time.time()
        if emotion != last_emotion or (current_time - last_emotion_time >= 30):
            last_emotion = emotion
            last_emotion_time = current_time

            print(f"\nDetected emotion: {emotion}")
            if emotion in emotion_tracks and emotion_tracks[emotion]:
                random_tracks = random.sample(emotion_tracks[emotion], min(5, len(emotion_tracks[emotion])))
                print(f"🎵 Suggested songs for '{emotion}':")
                for song in random_tracks:
                    print("   -", song)
            else:
                print(f"No tracks found for emotion '{emotion}'.")

    except Exception as e:
        print("Emotion detection error:", e)

    cv2.imshow('Emotion Detector', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
