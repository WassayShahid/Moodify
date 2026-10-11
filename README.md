# Moodify 🎧

Moodify reads your mood from your webcam and plays the songs from your Spotify playlist that match it.

- **Live mood detection in the browser.** [face-api.js](https://github.com/vladmandic/face-api) runs on your device, and no video is uploaded. Readings are smoothed so the picks don't flicker.
- **Playlist mood sorting.** Each track's [Last.fm](https://www.last.fm/api) tags are weighted into one of six moods: happy, energetic, calm, neutral, sad, angry. Results are cached in SQLite.
- **Mood breakdown chart.** See how your playlist splits across moods, and click a mood to pick it yourself.
- **Playable picks.** Recommendations show up as Spotify embeds, and you can save them as a private playlist on your account.
- **Demo playlist.** Try the app without pasting a playlist.

## Run it locally

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then fill in your keys
python app.py
```

Open http://127.0.0.1:5000. The landing page is at `/` and the app is at `/app`.

In the [Spotify dashboard](https://developer.spotify.com/dashboard), add `http://127.0.0.1:5000/callback` as a Redirect URI. Spotify no longer accepts `localhost` redirect URIs.

> **Spotify Premium is required.** Spotify only serves Web API requests for apps whose owner has an active Premium subscription. Without it, loading a playlist returns an error, but the demo playlist still works.

## Deploy (Render)

1. Push this repo to GitHub.
2. On [Render](https://render.com), choose **New → Blueprint** and pick the repo. It reads `render.yaml`.
3. Set `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `LASTFM_API_KEY`, and `SPOTIFY_REDIRECT_URI=https://<your-app>.onrender.com/callback`.
4. Add that same callback URL as a Redirect URI in the Spotify dashboard.

## Project layout

```
app.py                  Flask routes: landing, app, /api/playlist, /api/save, OAuth
moodify/music.py        Spotify loading, Last.fm tags, mood classification, cache
moodify/demo_playlist.json
templates/              base, landing, app pages
static/js/app.js        camera, face-api detection, picks, chart, save flow
static/css/style.css
```
