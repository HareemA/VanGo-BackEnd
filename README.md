# Description
- This Folder has the backend of mobile application VanGo
-  It has database script in database.py and the server is in server.py which is flask
-  Simply run server.py to run the server, the database is hosted on Render.
  (The render hosting expired, so you'll have to create a database called VanGo in your Postgres and then give your database credentials in database.py and server.py and then uncomment the #create_tables() function and run server)
-  Once connected access VanGo-Frontend repository to get frontend of the mobile application.
-  Publisher Enter and Leave uses webcam to send frames to server for facial detection.
