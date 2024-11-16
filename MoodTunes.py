import cv2
from deepface import DeepFace

# Initialize webcam
cap = cv2.VideoCapture(0)

while True:
    # Capture frame-by-frame
    ret, frame = cap.read()

    if not ret:
        print("Failed to capture image")
        break

    try:
        # Analyze the frame for emotion
        results = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)

        # Check if results is a list (multiple faces detected) or a dictionary (single face)
        if isinstance(results, list):
            emotion = results[0]['dominant_emotion']
        else:
            emotion = results['dominant_emotion']

        # Display the emotion on the screen
        cv2.putText(frame, f'Emotion: {emotion}', (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)

    except Exception as e:
        print("Error analyzing frame:", e)
        emotion = "Error"

    # Show the video frame with detected emotion
    cv2.imshow('Emotion Detector', frame)

    # Press 'q' to quit the video
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release the webcam and close windows
cap.release()
cv2.destroyAllWindows()
