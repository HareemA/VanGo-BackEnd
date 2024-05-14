import time
from flask import Flask, Response, request, jsonify
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
from database import *
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

channels = {}
channel_enter = {}
channel_leave = {}

channel_locks = {}
channel_locks_enter = {}
channel_locks_leave = {}

DEFAULT_ENCODINGS_PATH = "./output/encodings.pkl"
BOUNDING_BOX_COLOR = (0, 0, 255)
TEXT_COLOR = (255, 255, 255)
TRAINING_PATH = "./training"



def encode_new_face(file_path):
        try:
            print(file_path)
            path = file_path.replace("\\", "/")

            image = face_recognition.load_image_file(path)
            face_locations = face_recognition.face_locations(image, model="hog")
            face_encodings = face_recognition.face_encodings(image, face_locations)
        except Exception as e:
            print("Error in encoding ",e)

        return face_encodings


def encode_known_faces():
    child_ids = []
    encodings = []

    for filepath in Path(TRAINING_PATH).glob("*/*"):
        child_id = filepath.parent.name  
        image = face_recognition.load_image_file(filepath)

        face_locations = face_recognition.face_locations(image, model="hog")
        face_encodings = face_recognition.face_encodings(image, face_locations)

        for encoding in face_encodings:
            child_ids.append(child_id)
            encodings.append(encoding)

    child_encodings = {"ids": child_ids, "encodings": encodings}

    with open(DEFAULT_ENCODINGS_PATH, "wb") as f:
        pickle.dump(child_encodings, f)


#   RETURNS NAME ONLY
def recognize_faces(frame):
    loaded_encodings = get_all_encodings()
    np_frame = np.array(frame)

    face_locations = face_recognition.face_locations(np_frame, model="hog")
    face_encodings = face_recognition.face_encodings(np_frame, face_locations)

    for face_location in face_locations:
        top, right, bottom, left = face_location

    detected_ids=[]
    for face_encoding in face_encodings:
        child_id = _recognize_face(face_encoding, loaded_encodings)  # Use child_id instead of name
        print("In recognize face")
        if child_id:
            print("child id",child_id)
            name = get_child_name_by_id(child_id)  # Fetch child's name using the child_id from the database
            print(name)
            
            
            detected_ids.append(child_id)
        else:
            print("Child not detected")
            return None
  
    return detected_ids


def _recognize_face(unknown_encoding, loaded_encodings):
    max_matches = 0
    detected_id = None

    for child_id, encoding in loaded_encodings.items():
        match = face_recognition.compare_faces(encoding, unknown_encoding, tolerance=0.5)
        if match[0]:
            detected_id = child_id

    return detected_id






