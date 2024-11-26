import cv2
from deepface import DeepFace
import re
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import time
import os
import random  
from dotenv import load_dotenv

env_path = './keys.env'
load_dotenv(dotenv_path=env_path)

# Access the keys from the environment
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')

# Spotify API setup
client_credentials_manager = SpotifyClientCredentials(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET
)
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

# Function to extract playlist ID
def extract_playlist_id(playlist_url):
    match = re.search(r'playlist/([\w\d]+)', playlist_url)
    if match:
        return match.group(1)
    else:
        raise ValueError("Invalid playlist URL. Please provide a valid Spotify playlist link.")

# Function to get tracks from a playlist
def get_tracks_from_playlist(playlist_id):
    tracks = []
    results = sp.playlist_items(playlist_id)
    while results:
        tracks.extend(results['items'])
        results = sp.next(results) if results['next'] else None
    return tracks

# Function to get audio features for tracks
def get_audio_features_for_tracks(track_ids):
    features = []
    for i in range(0, len(track_ids), 100):  
        features.extend(sp.audio_features(track_ids[i:i + 100]))
    return features

# Function to calculate emotion from audio features
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

# Adding tracks to emotion dictionary
def add_tracks_to_emotion_dict(playlist_url):
    try:
        playlist_id = extract_playlist_id(playlist_url)
        tracks = get_tracks_from_playlist(playlist_id)
        track_ids = [track['track']['id'] for track in tracks if track['track']]  
        audio_features = get_audio_features_for_tracks(track_ids)
        
        for feature, track in zip(audio_features, tracks):
            if feature: 
                emotion = calculate_emotion(feature)
                track_name = track['track']['name']
                artist_name = track['track']['artists'][0]['name']
                emotion_tracks[emotion].append(f"{track_name} by {artist_name}")
        
        print("Tracks categorized by emotion:")
        for emotion, tracks in emotion_tracks.items():
            print(f"{emotion}: {len(tracks)} tracks")
    except Exception as e:
        print(f"Error adding tracks to emotion dictionary: {e}")

# Prompt for playlist URL
playlist_url = input("Enter your Spotify playlist URL: ")
add_tracks_to_emotion_dict(playlist_url)

# Webcam setup
cap = cv2.VideoCapture(0)
last_emotion = None
last_emotion_time = 0 

while True:
    ret, frame = cap.read()
    if not ret:
        print("Failed to capture image")
        break

    try:
        # Detect emotion using DeepFace
        results = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
        emotion = results[0]['dominant_emotion'] if isinstance(results, list) else results['dominant_emotion']

        # Display emotion on the frame
        cv2.putText(frame, f'Emotion: {emotion}', (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2, cv2.LINE_AA)

        # Check if emotion has changed or if enough time has passed
        current_time = time.time()
        if emotion != last_emotion or (current_time - last_emotion_time >= 30):
            last_emotion = emotion
            last_emotion_time = current_time

            # Suggest random 5 songs for the detected emotion
            if emotion in emotion_tracks and emotion_tracks[emotion]:
                random_tracks = random.sample(emotion_tracks[emotion], min(5, len(emotion_tracks[emotion])))
                print(f"Suggested songs for {emotion}:")
                for track in random_tracks:
                    print(track)
            else:
                print(f"No tracks available for the detected emotion: {emotion}")

    except Exception as e:
        print("Error analyzing frame:", e)

    # Show the webcam feed
    cv2.imshow('Emotion Detector', frame)

    # Quit if 'q' is pressed
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
