import requests
import time
import threading
import datetime
import geocoder

server_ip = "192.168.60.125"  # Replace with the server IP address
device_id = "2725e4fd-099b-495e-8a97-8b9a7d5eaa0b"  # Replace with a unique identifier for the device

def send_location():
    while True:
        location = geocoder.ip('me')
        if location.latlng:
            latitude, longitude = location.latlng
        timestamp = datetime.datetime.now().strftime('%H:%M:%S')

        payload = {
            'device_id': device_id,
            'latitude': latitude,
            'longitude': longitude,
            'timestamp': timestamp
        }

        url = f"http://{server_ip}:8080/update_location/{device_id}"  # Replace with the appropriate URL
        response = requests.post(url, json=payload)

        if response.status_code == 200:
            print("Location sent successfully.")
        else:
            print("Error sending location data to server.")

        time.sleep(5)  # Send data every 5 seconds

# Create a thread for sending location data
location_thread = threading.Thread(target=send_location)
location_thread.start()

# Your other application logic here...

# Wait for the location thread to finish (if needed)
location_thread.join()

print("Application finished.")
