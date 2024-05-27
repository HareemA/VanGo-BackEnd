import json
from flask import Flask, Response, request, jsonify, send_file
import threading
import face_recognition
import pickle
from collections import Counter
from PIL import Image, ImageDraw
import io
import numpy as np
import cv2
import os
from pathlib import Path
import urllib.parse
from FacRec_LiveStream import *
from database import *
import uuid
import base64
from pyfcm import FCMNotification
from queue import Queue
import requests
from threading import Lock
from openpyxl import Workbook
import pandas as pd
from openpyxl import load_workbook
import stripe


stripe.api_key = "sk_test_51P1Y69P5S3CJSYDgLH0TmWxQ8lys8yzXSRppa2W79pxvi6hObYbhbw28WehDjdS1xxvECzPSkY6RZyYUKIqOkDdB0011ybJtsX"
from attendance import *


enter_frame_queue = Queue()
leave_frame_queue  =Queue()
enter_frame_lock = Lock()
leave_frame_lock = Lock()
tokens = {}


app = Flask(__name__)

awsconn = psycopg2.connect(
    host="dpg-cp1puouct0pc73d68r70-a.oregon-postgres.render.com",
    port="5432",
    dbname="vango",
    user="vango_user",
    password="RNqJ7yync1oeqs6JvJJDDHurA15Ol1zQ"
)

#live stream API
@app.route("/video_feed/<string:child_id>", methods=["GET"])
def get_video_feed(child_id):
    # Get cameraURL from child ID
    camera_URL = get_cameraURL_from_childID(child_id)

    response = {
        "camera_URL": camera_URL
    }
    
    return jsonify(response)

    

#live location APIs

# Dictionary to store location data
location_data = {}

# Lock for ensuring thread-safe access to location_data
location_data_lock = threading.Lock()

@app.route("/update_location/<string:GPSdevice_id>", methods=["POST"])
def update_location(GPSdevice_id):
    if request.method == 'POST':
        
        data = request.get_json()
        if data:
            latitude = data.get('latitude')
            longitude = data.get('longitude')
            timestamp = data.get('timestamp')

            if latitude is not None and longitude is not None and timestamp is not None:
                with location_data_lock:
                    location_data[GPSdevice_id] = {
                        'latitude': latitude,
                        'longitude': longitude,
                        'timestamp': timestamp
                    }
                print(f"Location data received for {GPSdevice_id}:")
                print(f"Latitude: {latitude}, Longitude: {longitude}, Timestamp: {timestamp}")
                return 'Location data received successfully.'
            else:
                return 'Invalid location data format.', 400
        else:
            return 'No data found in the request.', 400
    else:
        return 'This endpoint only accepts POST requests.', 405




@app.route('/get_location/<string:child_id>', methods=["GET"])
def get_location(child_id):
    # Get GPSDevice ID from child ID
    device_id = get_GPSDevice_id_from_child_id(child_id)

    # Get real-time location using the GET request
    with location_data_lock:
        if device_id in location_data:
            return jsonify(location_data[device_id]), 200
        else:
            return "Location data not available", 404
        
#DATABASE APIs

#REGISTER PARENT API
@app.route("/add_parent", methods=["POST"])
def add_parent():  
    try: 
        
        data = request.get_json()
        print(data)
        cnic = data.get('cnic')
        if not check_cnic(cnic):
            return jsonify({"error": "Invalid CNIC. It should be exactly 13 characters."}), 400
        
        password = data.get('password')
        if not check_password(password):
            return jsonify({"error":"Password must contain Upper case letter,lower case letter, numbers and special characters"}),400
        
        phone_no = data.get('phoneNumber')
        if not check_no(phone_no):
            return jsonify({"error":"Phone number must be 11 digits"}),400
        
        email= data.get('email')
        if not check_email(email):
            return jsonify({"error":"Email incorrect"}),400
        
        name = data.get('fullName')
        address = data.get('address')
        id = data.get('userUid')

        fcmToken = data.get('expo_token')

        customer = stripe.Customer.create(
            email=email,
            name=name,
            # You can add more details here as needed
        )

        # Use the Stripe Customer ID in your database alongside the parent's information
        stripe_customer_id = customer['id']
        

        with awsconn, awsconn.cursor() as cur:
            cur.execute("""INSERT INTO parent(id, cnic, name, email, phone_no, password, address, fcm_token, stripe_customer_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;""",
                        (id, cnic, name, email, phone_no, password, address, fcmToken, stripe_customer_id))


            # parent_id = cur.fetchone()[0]
            parent_id = id 

            return jsonify({"message": "Parent added successfully!","parentId": str(parent_id)}),200

    except(Exception, psycopg2.DatabaseError) as error:
        print("Couldnt add parent",error)
        return jsonify({'error': 'Failed to add parent.', 'details': str(error)}), 500

 

@app.route('/sendFcmTokenAndParentId', methods=['POST'])
def sendFcmTokenAndParentId():
    try:
        data = request.json
        fcmToken = data['fcmToken']
        parentId = data['parentId']
        # Get the FCM token from the database for the given parent ID
        db_fcm_token = get_fcm_token_from_database(parentId)
        print("token:", db_fcm_token)
        # Compare the received FCM token with the one from the database
        if db_fcm_token != fcmToken:
            print("Not same")
            # Update the FCM token in the database
            update_parent_fcm_token(parentId, fcmToken)

        else:
            print("Tokens same")

        return jsonify({"success": True, "message": "FCM token and parent ID updated successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})



def store_picture(picture, child_id):  # Modify the function to use child_id instead of name
    # Save the picture in the training folder with the provided name (child_id)
    folder_path = os.path.join(TRAINING_PATH, str(child_id))
    os.makedirs(folder_path, exist_ok=True)
    picture_path = os.path.join(folder_path, f"{str(child_id)}.jpg")  # Use child_id instead of name
    with open(picture_path, "wb") as f:
        f.write(picture)

    # Update face encodings
    # encode_known_faces()
    encoding = encode_new_face(picture_path)

    return picture_path, encoding

def edit_picture(new_picture, child_id):
    # Check if the folder for the child exists
    folder_path = os.path.join(TRAINING_PATH, str(child_id))
    if os.path.exists(folder_path):
        # Delete the existing picture if it exists
        existing_picture_path = os.path.join(folder_path, f"{str(child_id)}.jpg")
        if os.path.exists(existing_picture_path):
            os.remove(existing_picture_path)
        
        # Write the new picture to the folder
        os.makedirs(folder_path, exist_ok=True)
        new_picture_path = os.path.join(folder_path, f"{str(child_id)}.jpg")
        with open(new_picture_path, "wb") as f:
            f.write(new_picture)
            return True

    return False


#REGISTER CHILD
@app.route("/register_child", methods=["POST"])    
def register_child():
    try:
        # print(request.form)
        # print(request.files)
        child_data_json = request.form.get("childData")

        # Convert JSON string to Python dictionary
        data = json.loads(child_data_json)
        # Parse the JSON data
        # print(data)
        #parent_id = data.get('parent_id')
        parent_id = data.get('parent_id')
        name = data.get('childName')
        cnic = data.get('bFormNumber')
        pickup_loc = data.get('pickupLocation')
        school = data.get('schoolName')
        dropoff_loc = data.get('dropOffLocation')

        # if "frontPhoto" not in request.files:
        #     print("No picture")
        #     return jsonify({"message": "Picture not provided"}), 400

        with awsconn:
            with awsconn.cursor() as cur:
                cur.execute("""SELECT stripe_customer_id FROM parent WHERE id = %s;""", (parent_id,))
                result = cur.fetchone()

        if not result:
            return jsonify({"error": "Parent not found"}), 404

        customer_id = result[0]

        child_subscription = stripe.Subscription.create(
        customer = customer_id,  # Parent's Stripe customer ID
        items=[{'price': 'price_1P1aYkP5S3CJSYDgfpOd616e'}],  # Price ID of monthly plan hardcoded for now
        payment_behavior='default_incomplete',
        payment_settings={'save_default_payment_method': 'on_subscription'},
        expand=['latest_invoice.payment_intent']
        )

        stripe_subscription_id = child_subscription['id']
        client_secret = child_subscription['latest_invoice']['payment_intent']['client_secret']
        

        print("Here")
        pic = data.get('picture')
        picture = base64.b64decode(pic)

        if picture is None:
            print("Empty")
            return

        with awsconn, awsconn.cursor() as cur:

            cur.execute("""CREATE EXTENSION IF NOT EXISTS "uuid-ossp";""")
            cur.execute("""INSERT INTO child(parent_id, name, cnic, pickup_loc, school, dropoff_loc, stripe_subscription_id, client_secret) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;""",
                        (parent_id, name, cnic, pickup_loc, school, dropoff_loc, stripe_subscription_id, client_secret))

            # Get the generated child ID
            child_id = cur.fetchone()[0]


            response_data = {
                    'subscriptionId': stripe_subscription_id,
                    'clientSecret': client_secret,
                    'childID' : child_id
                }

            # Save the picture in the training folder with the child's ID as the name
            picture_path, encoding = store_picture(picture, child_id)

            if encoding:
                encodings_data = psycopg2.Binary(pickle.dumps(encoding))
                print('Here')
                cur.execute("UPDATE child SET picture_path = %s , encoding =%s WHERE id = %s;", (picture_path, encodings_data, child_id))
            else: 
                raise Exception("No encodings")
            


            return jsonify(response_data),200

    except (Exception, psycopg2.DatabaseError) as error:
        print("Could not register child", error)
        return jsonify({'error': 'Failed to register child.', 'details': str(error)}), 500
    

@app.route("/edit_child", methods=["POST"])    
def edit_child():
    try:

        child_data_json = request.form.get("childData")

        # Convert JSON string to Python dictionary
        data = json.loads(child_data_json)
        child_id = data.get('child_id')
        pickup_loc = data.get('pickUpLoc')
        dropoff_loc = data.get('dropOffLoc')
        pic = data.get('picture')
        picture = base64.b64decode(pic)

        if pickup_loc:
            with awsconn, awsconn.cursor() as cur:
                cur.execute("update child set pickup_loc= %s where id=%s",(pickup_loc, child_id))
                print("Pickup updated")

        if dropoff_loc:
            with awsconn, awsconn.cursor() as cur:
                cur.execute("update child set dropoff_loc= %s where id=%s",(dropoff_loc, child_id))
                print("Dropoff updated")
        
        stat = False
        print("Picture: ", picture)
        if picture:
            stat = edit_picture(picture, child_id)
            print("Picture edited")

        print(stat)
        return jsonify({'success':'data edited sucessfully'}),200

    except (Exception, psycopg2.DatabaseError) as error:
        print("Could not register child", error)
        return jsonify({'error': 'Failed to register child.', 'details': str(error)}), 500
    


#API for getting Payment Status, Pickup Loc and DropOff Loc
@app.route("/get_payment_stat/<child_id>", methods=["POST"])
def retrieve_payment_stat(child_id):
    try:
         
        # Use the existing cursor
        with awsconn.cursor() as cur:
            # Execute the query
            cur.execute("""SELECT payment_stat, pickup_loc, dropoff_loc
                           FROM child
                           WHERE id = %s""", (child_id,))
            
            # Fetch the result
            result = cur.fetchone()
        
        # Check if child data exists
        if not result:
            return jsonify({"error": "Child data not found."}), 404
        
        # Extract payment status, pickup location, and dropoff location
        payment_stat, pickup_loc, dropoff_loc = result

        prices = {
          "Askari 7": {
            "APS Humayun": "10000",
            "APS Ordnance": "10500",
            "APS FortRoad": "11000",
          },
          "Askari 14": {
            "APS Humayun": "13500",
            "APS Ordnance": "12000",
            "APS FortRoad": "14500",
          },
          "Askari 13": {
            "APS Humayun": "14500",
            "APS Ordnance": "13000",
            "APS FortRoad": "12500",
          },
        }

        Jprice = prices[pickup_loc][dropoff_loc]
        print("prices: ",Jprice)

        
        # Return child data to the frontend
        return jsonify({
            "Jprice" : Jprice,
            "payment_status": payment_stat,
            "pickup_location": pickup_loc,
            "dropoff_location": dropoff_loc,
        }), 200
    
    except (Exception, psycopg2.DatabaseError) as error:
        print("Error processing request:", error)
        return jsonify({'error': 'Failed to retrieve child data.', 'details': str(error)}), 500



@app.route("/payment-sheet/<child_id>", methods=["POST"])
def payment_sheet(child_id):
    try:
        # Hardcoded child ID for demonstration
        # hardcoded_child_id = '4f3634f6-3755-48ad-8566-9223db673ef4'
        with awsconn:
            with awsconn.cursor() as cur:
                # Fetch the parent_id and stripe_customer_id using the child's ID
                cur.execute("""
                    SELECT parent.stripe_customer_id
                    FROM child
                    JOIN parent ON child.parent_id = parent.id
                    WHERE child.id = %s;
                    """, (child_id,))
                result = cur.fetchone()
                
                if not result:
                    return jsonify({"error": "Parent not found for the given child ID"}), 404

                stripe_customer_id = result[0]

        with awsconn.cursor() as cur:
            # Execute the query
            cur.execute("""SELECT pickup_loc, dropoff_loc
                           FROM child
                           WHERE id = %s""", (child_id,))
            
            # Fetch the result
            result = cur.fetchone()
        
        # Check if child data exists
        if not result:
            return jsonify({"error": "Child data not found."}), 404
        
        # Extract payment status, pickup location, and dropoff location
        pickup_loc, dropoff_loc = result

        prices = {
          "Askari 7": {
            "APS Humayun": "10000",
            "APS Ordnance": "10500",
            "PS FortRoad": "11000",
          },
          "Askari 14": {
            "APS Humayun": "13500",
            "APS Ordnance": "12000",
            "PS FortRoad": "14500",
          },
          "Askari 13": {
            "APS Humayun": "14500",
            "APS Ordnance": "13000",
            "PS FortRoad": "12500",
          },
        }

        Jprice = prices[pickup_loc][dropoff_loc]
        price = int(Jprice) *100

            
        # Create a PaymentIntent
        intent = stripe.PaymentIntent.create(
            amount= price,  # Example amount in cents
            currency='PKR',
            customer=stripe_customer_id,
            payment_method_types=['card'],
        )

        # Create an EphemeralKey
        ephemeralKey = stripe.EphemeralKey.create(
            customer=stripe_customer_id,
            stripe_version='2020-08-27',  # Specify the Stripe API version
        )

        # Return the PaymentSheet parameters
        return jsonify({
            "paymentIntent": intent.client_secret,
            "ephemeralKey": ephemeralKey.secret,
            "customer": stripe_customer_id,
        })

    except Exception as e:
        print(f"Error generating payment sheet parameters: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


 #cofirm payment function
def confirm_payment(child_id):
    try:
        with awsconn, awsconn.cursor() as cur:
            cur.execute("UPDATE child SET payment_stat = %s WHERE id = %s", (True, child_id))
            awsconn.commit()

    except (Exception, psycopg2.DatabaseError) as error:
        print("Couldn't confirm payment", error)

#API that confirms payment
@app.route("/confirm_payment_success/<child_id>", methods=["GET"])
def confirm_payment_success(child_id):
    try:
        bus_id = get_bus_ID()
        with awsconn, awsconn.cursor() as cur:
            cur.execute("UPDATE child SET payment_stat = %s, bus_id= %s WHERE id = %s", (True, bus_id, child_id))
            awsconn.commit()
            return jsonify({"message": "Payment confirmed successfully for child ID: {}".format(child_id)}), 200

    except (Exception, psycopg2.DatabaseError) as error:
        print("Couldn't confirm payment:", error)
        return jsonify({"error": "Failed to confirm payment.", "details": str(error)}), 500




@app.route("/get_children_data/<string:parent_id>", methods=["GET"])
def get_children_data(parent_id):
    try:
        with awsconn, awsconn.cursor() as cur:
            
            cur.execute("SELECT id, name, picture_path FROM child WHERE parent_id = %s;", (parent_id,))

            children_data = cur.fetchall()
            print(children_data)
            if not children_data:
                return jsonify({"message": "No children found for this parent ID"}), 404

            else:
                children = []

                for child in children_data:
                    child_info = {
                        "id": str(child[0]),
                        "name": child[1],  
                        "picture_base64": "",  
                    }
                    with open(child[2], "rb") as f:
                        picture_base64 = base64.b64encode(f.read()).decode("utf-8")
                    child_info["picture_base64"] = picture_base64

                    children.append(child_info)


                return jsonify(children)

    except (Exception, psycopg2.DatabaseError) as error:
        print("Error:", error)
        return jsonify({'message': 'Couldn\'t get children data!'}), 500
    
    

@app.route("/get_child_picture/<path:picture_path>", methods=["GET"])
def get_child_picture(picture_path):
    try:

        if os.path.exists(picture_path):
            with open(picture_path, "rb") as image_file:
                image_data = image_file.read()

            response = Response(image_data, mimetype="image/jpeg")
            response.headers["Content-Disposition"] = f"attachment; filename=child_picture.jpg"
            
            return response
        else:
            return jsonify({"message": "Picture not found"}), 404

    except Exception as error:
        print("Error:", error)
        return jsonify({'message': 'Couldn\'t get child picture!'}), 500
    

#new ones 
@app.route("/get_automatic_login_credentials/<string:parent_id>", methods=["POST"])
def get_automatic_login_credentials(parent_id):  
    try:
        with awsconn, awsconn.cursor() as cur:
            # Execute SQL query
            cur.execute("SELECT email, password FROM parent WHERE id = %s;", (parent_id,))
            parent_credentials = cur.fetchone()

            if parent_credentials:
                # Return the result
                return jsonify({"email": parent_credentials[0], "password": parent_credentials[1]}), 200
            else:
                # Return a message if no data found
                return jsonify({"message": "No parent found with ID: {}".format(parent_id)}), 404

    except (Exception, psycopg2.DatabaseError) as error:
        # Handle errors
        print("Error fetching parent credentials:", error)
        return jsonify({"message": "Error fetching parent credentials"}), 500
  

@app.route("/get_child_data_for_unregister/<child_id>", methods=["POST"])
def get_child_data_for_unregister(child_id):
    try:
         
        # Use the existing cursor
        with awsconn.cursor() as cur:
            # Execute the query
            cur.execute("""SELECT parent.email, parent.password, child.name, child.payment_stat
                FROM parent
                JOIN child ON parent.id = child.parent_id
                WHERE child.id = %s""", (child_id,))
            
            # Fetch the result
            result = cur.fetchone()
        
        # Check if child data exists
        if not result:
            return jsonify({"error": "Child data not found."}), 404
        
        # Extract payment status, pickup location, and dropoff location
        email, password, child_name, payment_stat = result

        return jsonify({
            "email": email,
            "password": password,
            "childName": child_name,
            "paymentStat": payment_stat,
        }), 200
    
    
    except (Exception, psycopg2.DatabaseError) as error:
        print("Error processing request:", error)
        return jsonify({'error': 'Failed to retrieve child data.', 'details': str(error)}), 500
    

@app.route('/unregister_child/<string:child_id>', methods=["GET"])
def unregister_child(child_id):
    try:
        # Use the existing cursor
        with awsconn.cursor() as cur:
            # Check if the child record exists
            cur.execute("SELECT id FROM child WHERE id = %s", (child_id,))
            result = cur.fetchone()

            if not result:
                return jsonify({"error": "Child not found."}), 404

            # Execute the deletion query
            cur.execute("DELETE FROM child WHERE id = %s", (child_id,))
            awsconn.commit()

        # Construct the folder path for the child's pictures
        PICTURE_FOLDER_PATH = './training'
        child_folder_path = os.path.join(PICTURE_FOLDER_PATH, child_id)

        # Check if the folder exists and delete it
        if os.path.exists(child_folder_path) and os.path.isdir(child_folder_path):
            shutil.rmtree(child_folder_path)

        return jsonify({"message": f"Child ID {child_id} unregistered successfully."}), 200

    except psycopg2.DatabaseError as db_error:
        print("Database error occurred:", db_error)
        return jsonify({'error': 'Failed to unregister child.', 'details': str(db_error)}), 500
    
    except Exception as error:
        print("Error occurred:", error)
        return jsonify({'error': 'An unexpected error occurred.', 'details': str(error)}), 500
    
    
from datetime import time

@app.route("/get_attendance/<string:childID>", methods=["GET"])
def get_attendance(childID):
    
    # Load the child's attendance data from the Excel file
    excel_filename = f"./attendance/{childID}.xlsx"
    try:
        df = pd.read_excel(excel_filename)
        
        # Convert the 'Date' field to string format
        df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
        
        # Convert the 'Time' field to string format
        df['Time'] = df['Time'].apply(lambda x: x.strftime('%H:%M:%S') if isinstance(x, time) else x)
        
        # Convert the DataFrame to a list of dictionaries
        attendance_data = df.values.tolist()
        
        print("Received attendance list:", attendance_data)
        
        # Return the attendance data as JSON
        return jsonify(attendance_data)
    
    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"error": str(e)})


@app.route("/video_feed_enter", methods=["POST"])
def video_feed_enter():
    if request.method == 'POST':
        if 'frame' in request.files:
            frame = request.files['frame'].read()
            nparr = np.fromstring(frame, np.uint8)
            frame_np = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            attendance_enter(frame_np)
            
            return 'Frame received successfully.'

        else:
            return 'No frame found in the request.', 400
    else:
        return 'This endpoint only accepts POST requests.', 405
    

@app.route("/video_feed_leave", methods=["POST"])
def video_feed_leave():
    if request.method == 'POST':
        if 'frame' in request.files:
            frame = request.files['frame'].read()
            nparr = np.fromstring(frame, np.uint8)
            frame_np = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            attendance_leave(frame_np)
            
            return 'Frame received successfully.'

        else:
            return 'No frame found in the request.', 400
    else:
        return 'This endpoint only accepts POST requests.', 405
    

@app.route("/update_url", methods=["POST"])
def update_url():
    try:
        data = request.json
        yt_url = data['url']
        with awsconn.cursor() as cur:
                cur.execute("UPDATE camera SET url = %s", (yt_url,))

        awsconn.commit()
        return 'URL updated successfully.'

    except Exception as e:
        print("Exception ",e)
        return 'URL not updated successfully.'

    

if __name__ == "__main__":

    # attendance_thread_enter = threading.Thread(target=attendance_thread_enter, args=(stop_event_enter,))
    # attendance_thread_enter.start()

    # attendance_thread_leave = threading.Thread(target=attendance_thread_leave, args=(stop_event_enter,))
    # attendance_thread_leave.start()
    
    app.run(host='0.0.0.0', port=8080)

    # stop_event_enter.set()
    # stop_event_leave.set()
  

