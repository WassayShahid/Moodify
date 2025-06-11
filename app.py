from flask import Flask, render_template, request
from MoodTunes import process_playlist, capture_frame, analyze_frame, recommend_tracks

app = Flask(__name__)
emotion_tracks = {}

@app.route('/', methods=['GET', 'POST'])
def index():
    global emotion_tracks
    if request.method == 'POST':
        playlist_url = request.form.get('playlist')
        emotion_tracks = process_playlist(playlist_url)
        return render_template('index.html', success=True)
    return render_template('index.html', success=False)

@app.route('/recommend')
def recommend():
    frame = capture_frame()
    emotion = analyze_frame(frame)
    recommendations = recommend_tracks(emotion, emotion_tracks)
    return render_template('index.html', emotion=emotion, recommendations=recommendations, success=True)

if __name__ == '__main__':
    app.run(debug=True)
