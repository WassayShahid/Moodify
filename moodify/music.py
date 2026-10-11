"""Playlist loading and mood classification.

Spotify supplies the tracks; Last.fm's crowd-sourced tags decide each track's mood
(Spotify retired its audio-features endpoint for new apps in late 2024).
"""
import os
import re
import sqlite3
import json
import math
import threading
from concurrent.futures import ThreadPoolExecutor

import requests
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

MOODS = ["happy", "energetic", "calm", "neutral", "sad", "angry"]
MAX_TRACKS = 300

# Tag vocabulary. Most Last.fm tags are genres, so explicit mood words (weight 3+) are
# trusted far more than genre hints (weight <= 1.5). Tag counts (0-100) are square-rooted
# so one dominant genre tag can't drown out a rarer but more telling mood tag.
TAG_MOODS = {
    "happy": {"happy": 4, "feel good": 4, "feelgood": 4, "fun": 3, "upbeat": 3, "joy": 4,
              "joyful": 4, "cheerful": 4, "sunshine": 3, "uplifting": 3, "positive": 3,
              "summer": 1.5, "catchy": 1, "disco": 1.5, "funk": 1.5, "feel-good": 4,
              "psychedelic pop": 0.5, "indie pop": 0.5, "dance-pop": 1},
    "energetic": {"energetic": 4, "party": 3, "hype": 4, "workout": 4, "banger": 4,
                  "high energy": 4, "pump up": 4, "fast": 3, "dance": 1.5, "edm": 1.5,
                  "electronic": 0.75, "club": 1.5, "house": 1, "drum and bass": 1.5,
                  "trap": 1, "rap": 0.5, "hip-hop": 0.5, "hip hop": 0.5, "rock": 0.5,
                  "pop rock": 0.5, "electropop": 1},
    "calm": {"chill": 4, "calm": 4, "relaxing": 4, "soothing": 4, "mellow": 4,
             "chillout": 4, "peaceful": 4, "relax": 4, "soft": 3, "sleep": 3, "dreamy": 3,
             "beautiful": 1.5, "ambient": 1.5, "lo-fi": 1.5, "lofi": 1.5, "acoustic": 1,
             "dream pop": 1.5, "neo-soul": 1, "soul": 0.5, "jazz": 1, "folk": 1,
             "piano": 1, "singer-songwriter": 0.5, "indie folk": 1, "rnb": 0.5},
    "sad": {"sad": 4, "melancholy": 4, "melancholic": 4, "depressing": 4, "heartbreak": 4,
            "lonely": 4, "breakup": 4, "crying": 4, "sad songs": 4, "bittersweet": 3,
            "emotional": 2, "ballad": 2, "emo": 1.5, "slowcore": 1.5},
    "angry": {"angry": 4, "aggressive": 4, "rage": 4, "intense": 2, "heavy": 2, "dark": 1,
              "metal": 1.5, "metalcore": 1.5, "nu metal": 1.5, "thrash metal": 1.5,
              "hardcore": 1.5, "punk": 1, "grunge": 1, "hard rock": 1, "drill": 1},
}

# When the detected mood has no tracks, borrow from the closest moods instead.
NEIGHBOURS = {
    "happy": ["energetic", "calm", "neutral"],
    "energetic": ["happy", "angry", "neutral"],
    "calm": ["neutral", "sad", "happy"],
    "neutral": ["calm", "happy", "energetic"],
    "sad": ["calm", "neutral"],
    "angry": ["energetic", "sad", "neutral"],
}

_CACHE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "instance", "tags.db")
_cache_lock = threading.Lock()
_sp = None


def _spotify():
    global _sp
    if _sp is None:
        _sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
            client_id=os.getenv("SPOTIFY_CLIENT_ID"),
            client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        ), requests_timeout=15)
    return _sp


def extract_playlist_id(url):
    match = re.search(r"playlist[/:]([A-Za-z0-9]{22})", url or "")
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9]{22}", (url or "").strip()):
        return url.strip()
    raise ValueError("That doesn't look like a Spotify playlist link.")


# --- Last.fm tag cache -----------------------------------------------------------

def _db():
    os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
    conn = sqlite3.connect(_CACHE_PATH, timeout=10)
    conn.execute("CREATE TABLE IF NOT EXISTS tags (key TEXT PRIMARY KEY, tags TEXT)")
    return conn


def _cache_get(key):
    with _cache_lock, _db() as conn:
        row = conn.execute("SELECT tags FROM tags WHERE key = ?", (key,)).fetchone()
    return json.loads(row[0]) if row else None


def _cache_set(key, tags):
    with _cache_lock, _db() as conn:
        conn.execute("INSERT OR REPLACE INTO tags VALUES (?, ?)", (key, json.dumps(tags)))


def _lastfm(method, **params):
    try:
        r = requests.get("https://ws.audioscrobbler.com/2.0/", params={
            "method": method, "api_key": os.getenv("LASTFM_API_KEY"),
            "format": "json", "autocorrect": 1, **params,
        }, timeout=10)
        r.raise_for_status()
        tags = r.json().get("toptags", {}).get("tag", [])
        return [(t["name"].lower(), int(t.get("count", 0))) for t in tags[:25]]
    except (requests.RequestException, ValueError, KeyError):
        return None


def get_tags(name, artist):
    """Track tags, falling back to artist tags for obscure tracks. Cached on disk."""
    key = f"{artist}|{name}".lower()
    cached = _cache_get(key)
    if cached is not None:
        return cached
    tags = _lastfm("track.gettoptags", track=name, artist=artist)
    if not tags:
        artist_tags = _cache_get(f"artist|{artist}".lower())
        if artist_tags is None:
            artist_tags = _lastfm("artist.gettoptags", artist=artist)
            if artist_tags is not None:
                _cache_set(f"artist|{artist}".lower(), artist_tags)
        tags = artist_tags
    if tags is None:  # network failure: don't cache, try again next time
        return []
    _cache_set(key, tags)
    return tags


def classify(tags):
    scores = {mood: 0.0 for mood in TAG_MOODS}
    for tag, count in tags:
        for mood, vocab in TAG_MOODS.items():
            if tag in vocab:
                scores[mood] += vocab[tag] * (1 + math.sqrt(count))
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "neutral"


# --- Playlist ----------------------------------------------------------------------

def _classify_tracks(tracks):
    with ThreadPoolExecutor(max_workers=6) as pool:
        all_tags = list(pool.map(lambda t: get_tags(t["name"], t["artist"]), tracks))
    counts = {mood: 0 for mood in MOODS}
    for track, tags in zip(tracks, all_tags):
        track["mood"] = classify(tags)
        counts[track["mood"]] += 1
    return counts


def load_demo():
    """A built-in playlist so the site works without a Spotify API call."""
    path = os.path.join(os.path.dirname(__file__), "demo_playlist.json")
    with open(path, encoding="utf-8") as f:
        tracks = json.load(f)
    return {"id": None, "name": "Moodify Demo Mix", "owner": "Moodify", "image": None,
            "tracks": tracks, "counts": _classify_tracks(tracks)}


def load_playlist(url):
    sp = _spotify()
    playlist_id = extract_playlist_id(url)
    try:
        meta = sp.playlist(playlist_id, fields="name,images,owner(display_name)")
    except spotipy.SpotifyException as e:
        if e.http_status == 404:
            raise ValueError("Spotify couldn't find that playlist. Make sure it's public "
                             "(Spotify-made playlists like 'Today's Top Hits' can't be read by third-party apps).")
        if e.http_status == 403 and "premium" in str(e).lower():
            raise ValueError("Spotify is blocking this app: the Spotify developer account that owns it "
                             "needs an active Premium subscription. Try the demo playlist instead.")
        raise

    tracks = []
    page = sp.playlist_items(playlist_id, additional_types=("track",),
                             fields="items(track(id,name,type,artists(name),album(images))),next")
    while page and len(tracks) < MAX_TRACKS:
        for item in page["items"]:
            t = item.get("track")
            if t and t.get("id") and t.get("type", "track") == "track":
                images = t.get("album", {}).get("images") or []
                tracks.append({
                    "id": t["id"],
                    "name": t["name"],
                    "artist": t["artists"][0]["name"] if t["artists"] else "Unknown",
                    "image": images[-1]["url"] if images else None,
                })
        page = sp.next(page) if page.get("next") else None
    tracks = tracks[:MAX_TRACKS]
    counts = _classify_tracks(tracks)

    images = meta.get("images") or []
    return {
        "id": playlist_id,
        "name": meta.get("name", "Playlist"),
        "owner": (meta.get("owner") or {}).get("display_name"),
        "image": images[0]["url"] if images else None,
        "tracks": tracks,
        "counts": counts,
    }
