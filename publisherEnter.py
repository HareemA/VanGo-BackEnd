import cv2
import requests

server_ip = "147.182.229.215"  # Replace with the server laptop IP address
#server_ip = "192.168.100.10"  # Replace with the server laptop IP address
channel_name = "f8b95fae-2437-4106-b0bd-a53f12b377ce" # Replace with the desired channel name Camera ID

video = cv2.VideoCapture(0)  # Use webcam index 0 (default)

while True:
    success, frame = video.read()
    if not success:
        break
    else:
        _, buffer = cv2.imencode('.jpg', frame)
        frame_data = buffer.tobytes()

        # Send the frame to the server using the channel name
        url = f"http://{server_ip}:8080/video_feed_enter"
        files = {'frame': ('frame.jpg', frame_data, 'image/jpeg')}
        response = requests.post(url, files=files)

        if response.status_code != 200:
            print("Error sending frame to server.")


