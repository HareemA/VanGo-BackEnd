import cv2
import requests

server_ip = "192.168.197.125"  # Replace with the server laptop IP address
channel_name = "39f61b89-661e-4f15-84c1-7bf770ba56f9" # Replace with the desired channel name Camera ID

video = cv2.VideoCapture(0)  # Use webcam index 0 (default)

while True:
    success, frame = video.read()
    if not success:
        break
    else:
        _, buffer = cv2.imencode('.jpg', frame)
        frame_data = buffer.tobytes()

        # Send the frame to the server using the channel name
        url = f"http://{server_ip}:8080/video_feed/{channel_name}"
        files = {'frame': ('frame.jpg', frame_data, 'image/jpeg')}
        response = requests.post(url, files=files)

        if response.status_code != 200:
            print("Error sending frame to server.")

    # Exit the loop when 'q' key is pressed
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

video.release()
cv2.destroyAllWindows()
