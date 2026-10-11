import os
import secrets

import spotipy
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from spotipy.cache_handler import FlaskSessionCacheHandler
from spotipy.oauth2 import SpotifyOAuth

from moodify.music import MOODS, load_demo, load_playlist

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_NAME="moodify", SESSION_COOKIE_SAMESITE="Lax")

MOOD_LABELS = {
    "happy": "Happy", "energetic": "Energetic", "calm": "Calm",
    "neutral": "Neutral", "sad": "Sad", "angry": "Angry",
}


def oauth():
    return SpotifyOAuth(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:5000/callback"),
        scope="playlist-modify-private",
        cache_handler=FlaskSessionCacheHandler(session),
        show_dialog=False,
    )


@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/app")
def main_app():
    return render_template("app.html", moods=MOODS, mood_labels=MOOD_LABELS)


@app.post("/api/playlist")
def api_playlist():
    data = request.get_json(silent=True) or {}
    try:
        if data.get("demo"):
            return jsonify(load_demo())
        return jsonify(load_playlist(data.get("url", "")))
    except ValueError as e:
        return jsonify(error=str(e)), 400
    except spotipy.SpotifyException as e:
        app.logger.warning("Spotify error: %s", e)
        return jsonify(error="Spotify couldn't load that playlist. Check the link and that it's public."), 502


@app.route("/login")
def login():
    return redirect(oauth().get_authorize_url())


@app.route("/callback")
def callback():
    if request.args.get("error"):
        return redirect(url_for("main_app"))
    oauth().get_access_token(request.args["code"], as_dict=False)
    return redirect(url_for("main_app", resume="save"))


@app.post("/api/save")
def api_save():
    auth = oauth()
    if not auth.validate_token(auth.get_cached_token()):
        return jsonify(login_url=url_for("login")), 401

    data = request.get_json(silent=True) or {}
    mood = data.get("mood") if data.get("mood") in MOODS else "neutral"
    track_ids = [t for t in data.get("track_ids", []) if isinstance(t, str)][:100]
    if not track_ids:
        return jsonify(error="No tracks to save."), 400

    sp = spotipy.Spotify(auth_manager=auth)
    playlist = sp.current_user_playlist_create(
        f"Moodify · {MOOD_LABELS[mood]}", public=False,
        description=f"Songs picked by Moodify for a {mood} mood.",
    )
    sp.playlist_add_items(playlist["id"], track_ids)
    return jsonify(url=playlist["external_urls"]["spotify"], name=playlist["name"])


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
