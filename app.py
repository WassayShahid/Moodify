from flask import Flask, render_template, request, redirect, session, url_for
from MoodTunes import process_playlist, capture_frame, analyze_frame, recommend_tracks, extract_playlist_id
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

load_dotenv('./keys.env')

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecret")
app.config['SESSION_COOKIE_NAME'] = 'MoodifySession'


sp_oauth = SpotifyOAuth(
    client_id=os.getenv('CLIENT_ID'),
    client_secret=os.getenv('CLIENT_SECRET'),
    redirect_uri='http://localhost:5000/callback',
    scope='playlist-modify-public playlist-modify-private user-read-private'
)

emotion_tracks = {}
last_emotion = None
last_recommendations = []

@app.route('/', methods=['GET', 'POST'])
def index():
    global emotion_tracks, last_emotion, last_recommendations
    access_token = session.get('token_info', {}).get('access_token')
    playlist_id = None

    if request.method == 'POST':
        playlist_url = request.form.get('playlist')
        session['last_playlist_url'] = playlist_url
        playlist_id = extract_playlist_id(playlist_url)

        emotion_tracks = process_playlist(playlist_url)
        session['emotion_tracks'] = emotion_tracks
        session['playlist_id'] = playlist_id
        last_emotion = None
        last_recommendations = []

        return render_template(
            'index.html',
            success=True,
            access_token=access_token,
            playlist_id=playlist_id
        )

    return render_template('index.html', success=False, access_token=access_token)





@app.route('/recommend', methods=['POST'])
def recommend():
    global last_emotion, last_recommendations
    access_token = session.get('token_info', {}).get('access_token')
    emotion_tracks = session.get('emotion_tracks', {})
    playlist_id = session.get('playlist_id')

    try:
        frame = capture_frame()
        emotion = analyze_frame(frame)
    except Exception as e:
        return render_template('index.html', emotion="unknown", recommendations=[], error=str(e), playlist_id=playlist_id)

    recommendations = recommend_tracks(emotion, emotion_tracks)
    last_emotion = emotion
    last_recommendations = recommendations

    return render_template(
        'index.html',
        emotion=emotion,
        recommendations=recommendations,
        success=True,
        playlist_id=playlist_id
    )


@app.route('/login')
def login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code, as_dict=True)
    session['token_info'] = token_info
    return redirect(url_for('save_playlist'))

@app.route('/save_playlist')
def save_playlist():
    token_info = session.get('token_info')
    if not token_info:
        return redirect(url_for('login'))

    sp = spotipy.Spotify(auth=token_info['access_token'])

    user = sp.current_user()
    user_id = user['id']
    playlist_name = f"Moodify - {last_emotion.capitalize()} Picks"

    playlist = sp.user_playlist_create(user=user_id, name=playlist_name, public=False)
    track_uris = []

    for track in last_recommendations:
        name, artist = track.split(' by ')
        results = sp.search(q=f"track:{name} artist:{artist}", type='track', limit=1)
        items = results['tracks']['items']
        if items:
            track_uris.append(items[0]['uri'])

    if track_uris:
        sp.playlist_add_items(playlist_id=playlist['id'], items=track_uris)

    return f"✅ Playlist '{playlist_name}' created and saved to your Spotify account."

if __name__ == '__main__':
    app.run(debug=True)
