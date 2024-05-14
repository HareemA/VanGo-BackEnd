import pickle
import shutil
import psycopg2
import os
import uuid
#conn = psycopg2.connect(host="localhost", dbname="vango", user="postgres",password="12345")
# awsconn = psycopg2.connect(
#     host="13.49.67.238",
#     port="5432",
#     dbname="VanGo",
#     user="postgres",
#     password="12345"
# )

# awsconn = psycopg2.connect(
#     host="dpg-cp1puouct0pc73d68r70-a",
#     port="5432",
#     dbname="VanGo",
#     user="vango_user",
#     password="12345"
# )

awsconn = psycopg2.connect(
    host="dpg-cp1puouct0pc73d68r70-a.oregon-postgres.render.com",
    port="5432",
    dbname="vango",
    user="vango_user",
    password="RNqJ7yync1oeqs6JvJJDDHurA15Ol1zQ"
)

def create_tables():
    try:
        with awsconn, awsconn.cursor() as cur:
            #creating parent's table  #URGENT TOdo: add stripe_customer_id column
            cur.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")

            cur.execute("""create table if not exists parent(
                        id VARCHAR PRIMARY KEY,
                        cnic VARCHAR(13) NOT NULL CHECK (LENGTH(cnic)=13) UNIQUE,
                        name VARCHAR(50) NOT NULL,
                        email VARCHAR(50) NOT NULL UNIQUE,
                        phone_no VARCHAR(11) NOT NULL CHECK (LENGTH(phone_no)=11 AND phone_no LIKE '0%'),
                        password VARCHAR NOT NULL CHECK (LENGTH(password) >= 8 AND password ~ '[0-9]' AND password ~ '[A-Z]' OR password ~ '[a-z]' AND password ~ '[!@#$%^&*()]'),
                        address VARCHAR NOT NULL,
                        fcm_token VARCHAR,
                        stripe_customer_id VARCHAR(255)
            )
    """)

            #creating camera's table
            cur.execute("""create table if not exists camera(
                        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                        URL varchar,
                        type VARCHAR
            )
    """)
            
            cur.execute("""create table if not exists GPSDevice(
                        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                        model varchar
            )
    """)

            #creating bus' table
            cur.execute("""create table if not exists bus(
                        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                        liscenes_no INT NOT NULL UNIQUE,
                        camera_id UUID,
                        pickup_loc varchar,
                        dropoff_loc varchar,
                        gpsID UUID,
                        FOREIGN KEY(camera_id) references camera(id),
                        FOREIGN KEY(gpsID) references GPSDevice(id)
            )
    """)

            #creating child's table
            cur.execute("""create table if not exists child(
                        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                        parent_id VARCHAR,
                        name VARCHAR(50) NOT NULL,
                        cnic VARCHAR(13) NOT NULL CHECK(LENGTH(cnic)=13) UNIQUE,
                        pickup_loc VARCHAR,
                        school VARCHAR,
                        encoding bytea,
                        dropoff_loc VARCHAR,
                        bus_id UUID,
                        picture_path VARCHAR,
                        payment_stat bool,
                        is_present bool,
                        stripe_subscription_id VARCHAR(255),
                        client_secret VARCHAR(255),
                        FOREIGN KEY(parent_id) references parent(id),
                        FOREIGN KEY(bus_id) references bus(id)
            )
                        
    """)
            
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")

            table_names = cur.fetchall()

            # Print the table names
            print("Table Names:")
            for name in table_names:
                print(name[0]) 


    except(Exception, psycopg2.DatabaseError) as error:
        print("Couldnt create tables",error)


def drop_all_tables():
    try:
        with awsconn, awsconn.cursor() as cur:
            # Get the list of table names from the database
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
            table_names = cur.fetchall()

            # Drop each table one by one
            for table in table_names:
                table_name = table[0]
                cur.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE;")

            print("All tables dropped successfully!")

    except (Exception, psycopg2.DatabaseError) as error:
        print("Error:", error)

def get_parent_by_email(email):
    try:
        with awsconn, awsconn.cursor() as cur:
            cur.execute("SELECT * FROM parent WHERE email = %s;", (email,))
            parent_data = cur.fetchone()

            if parent_data:
                return {
                    "id": str(parent_data[0]),  # Convert UUID to string for JSON serialization
                    "cnic": parent_data[1],
                    "name": parent_data[2],
                    "email": parent_data[3],
                    "phone_no": parent_data[4],
                    "password": parent_data[5],
                    "address": parent_data[6]
                }
            else:
                return None

    except (Exception, psycopg2.DatabaseError) as error:
        print("Error:", error)



def get_parent(id):
    try:
        with awsconn, awsconn.cursor() as cur:
            cur.execute("SELECT * FROM parent WHERE id = %s;", (id,))
            parent_data = cur.fetchone()

            if parent_data:
                parent = {
                    "cnic": parent_data[1],
                    "name": parent_data[2],
                    "email": parent_data[3],
                    "phone_no": parent_data[4],
                    "password": parent_data[5],
                    "address": parent_data[6]
                }
                print("Parent Details:")
                print(parent)
            else:
                print(f"No parent found with ID {id}")

    except(Exception, psycopg2.DatabaseError) as error:
        print("Could not get parent record:", error)


def get_all_parents():
    try:
        with awsconn, awsconn.cursor() as cur:
            cur.execute("SELECT * FROM parent;")
            parents_data = cur.fetchall()

            for parent_data in parents_data:
                parent = {
                    "id": parent_data[0],
                    "cnic": parent_data[1],
                    "name": parent_data[2],
                    "email": parent_data[3],
                    "phone_no": parent_data[4],
                    "address": parent_data[6]
                }
                print(parent)

    except (Exception, psycopg2.DatabaseError) as error:
        print("Error:", error)

def get_parent_ids_from_child_id(detected_ids):
    parent_ids = {}

    try:
        with awsconn, awsconn.cursor() as cur:
            for child_id in detected_ids:
                query = "SELECT parent_id FROM child WHERE id = %s"
                cur.execute(query, (child_id,))
                parent_id = cur.fetchone()
                if parent_id:
                    parent_ids[child_id] = parent_id[0]
    except Exception as e:
        print("Error while fetching parent IDs:", e)

    return parent_ids


def get_parent_tokens(parent_ids):
    parent_tokens = {}

    try:
        with awsconn, awsconn.cursor() as cur:
            for parent_id in parent_ids:
                query = "SELECT fcm_token FROM parent WHERE id = %s"
                cur.execute(query, (parent_id,))
                fcm_token = cur.fetchone()
                # adds parent id as key and token as value
                if fcm_token:
                    parent_tokens[parent_id] = fcm_token[0]
    except Exception as e:
        print("Error while fetching parent tokens:", e)

    return parent_tokens

def get_parent_id_and_token(child_id):
    try:
        with awsconn, awsconn.cursor() as cur:   
                query = "SELECT p.id , p.fcm_token FROM parent as p join child as c ON p.id = c.parent_id WHERE c.id = %s"
                cur.execute(query, (child_id,))
                data = cur.fetchone()

                if data:
                    return data

    except Exception as e:
        print("Error while fetching parent IDs:", e)


def update_parent_fcm_token(parent_id, fcm_token):
    try:
        with awsconn, awsconn.cursor() as cur:
            print("Updating parent")
            update_query = "UPDATE parent SET fcm_token = %s WHERE id = %s"
            cur.execute(update_query, (fcm_token, parent_id))
            awsconn.commit()
            print("Parent's FCM token updated successfully")
    except psycopg2.Error as e:
        awsconn.rollback()
        print("Error updating parent's FCM token:", e)


def get_fcm_token_from_database(parent_id):
    try:
        with awsconn, awsconn.cursor() as cur:
            select_query = "SELECT fcm_token FROM parent WHERE id = %s"
            cur.execute(select_query, (parent_id,))
            fcm_token = cur.fetchone()[0]
            return fcm_token
    except (Exception, psycopg2.DatabaseError) as error:
        print("Error:", error)
        return None



def get_all_children():
    try:
        with awsconn, awsconn.cursor() as cur:
            cur.execute("SELECT * FROM child;")
            children_data = cur.fetchall()

            if not children_data:
                print("No children found.")
            else:
                for child_data in children_data:
                    child = {
                        "id": str(child_data[0]),  # Convert UUID to string for JSON serialization
                        "parent_id": str(child_data[1]),
                        "name": child_data[2],
                        "bform": child_data[3],
                        "pickup_loc": child_data[4],
                        "school": child_data[5],
                        "dropoff_loc": child_data[6],
                        "bus_id": str(child_data[7]),
                        "picture_path": child_data[8]
                    }
                    print("Child ID:", child["id"])
                    print("Parent ID:", child["parent_id"])
                    print("Name:", child["name"])
                    print("B-Form:", child["bform"])
                    print("Pickup Location:", child["pickup_loc"])
                    print("School:", child["school"])
                    print("Dropoff Location:", child["dropoff_loc"])
                    print("Bus ID:", child["bus_id"])
                    print("Picture path:", child["picture_path"])
                    print("-" * 30)

    except (Exception, psycopg2.DatabaseError) as error:
        print("Error:", error)


def get_all_encodings():
    with awsconn, awsconn.cursor() as cur:
        cur.execute("SELECT id, encoding FROM child where encoding is not NULL")
        encodings_db = cur.fetchall()
        loaded_encodings = {}
        if encodings_db:
            # print("encodings: ", encodings_db)
            for row in encodings_db:
                id , encodings = row
                encodings = pickle.loads(encodings)
                loaded_encodings[id] = encodings

        return loaded_encodings

        #     loaded_encodings = {id_: pickle.loads(encoding) for id_, encoding in encodings_db if encoding is not None}
        #     return loaded_encodings
        # return {}

# print(get_all_encodings())

def check_password(password):
    return (
        len(password) >= 8 and
        any(char.isdigit() for char in password) and
        any(char.isupper() for char in password) or
        any(char.islower() for char in password) and
        any(char in '!@#$%^&*()' for char in password)
    )

def get_child_name_by_id(child_id):
    try:
        with awsconn, awsconn.cursor() as cur:
            cur.execute("SELECT name FROM child WHERE id = %s;", (child_id,))
            child_name = cur.fetchone()

            if not child_name:
                return None

            return child_name[0]

    except (Exception, psycopg2.DatabaseError) as error:
        print("Error:", error)
        return None


def get_cameraURL_from_childID(child_id):
    try:
        with awsconn, awsconn.cursor() as cur:
            cur.execute("SELECT c.URL FROM child ch JOIN bus b ON ch.bus_id = b.id JOIN camera c ON b.camera_id = c.id WHERE ch.id = %s", (child_id,))
            URL = cur.fetchone()

            if URL is None:
                print("No camera URL found for child_id: {}".format(child_id))
                return None

            return URL[0]

    except psycopg2.Error as e:
        print("Error retrieving camera URL:", e)
        return None


def get_GPSDevice_id_from_child_id(child_id):
    try:
        with awsconn, awsconn.cursor() as cur:
            # Retrieve bus_id from the child table using the child_id
            cur.execute("SELECT bus_id FROM child WHERE id = %s", (child_id,))
            bus_id = cur.fetchone()

            if bus_id:
                # Retrieve camera_id and GPSDevice_id from the bus table using the bus_id
                cur.execute("SELECT gpsid FROM bus WHERE id = %s", (bus_id,))
                gps_id = cur.fetchone()

            if not gps_id:
                print("GPS id not found")
                return None

            return gps_id[0]

    except(Exception, psycopg2.DatabaseError) as error:
        print("Could not get GPS ID", error)

def get_child_presence_status(child_id):
    try:
        with awsconn, awsconn.cursor() as cur:
            query = "SELECT is_present FROM child WHERE id = %s;"
            cur.execute(query, (child_id,))
            result = cur.fetchone()

            if result:
                return result[0]  # Assuming is_present is a boolean column
            else:
                return None

    except Exception as e:
        print("Error fetching child presence status:", e)
        return None


def get_child_name_and_present_status(child_id):
    try:
        with awsconn, awsconn.cursor() as cur:
            query = "SELECT name, is_present FROM child WHERE id = %s;"
            cur.execute(query, (child_id,))
            result = cur.fetchone()
            print(result)
            return result

    except Exception as e:
        print("Error fetching child presence status:", e)
        return None

def update_child_presence_status(child_id, is_present):
    try:
        with awsconn, awsconn.cursor() as cur:
            query = "UPDATE child SET is_present = %s WHERE id = %s;"
            cur.execute(query, (is_present, child_id))
            awsconn.commit()

    except Exception as e:
        print("Error updating child presence status:", e)
        awsconn.rollback()


def check_cnic(cnic):
    return len(cnic) == 13

def check_no(phone_no):
    return len(phone_no) == 11

def check_email(email):
    return '@' in email


def assign_bus_to_child(child_id, bus_id):
    try:
        with awsconn, awsconn.cursor() as cur:
            cur.execute("UPDATE child SET bus_id = %s WHERE id = %s AND payment_stat = %s", (bus_id, child_id, True))
            awsconn.commit()

    except (Exception, psycopg2.DatabaseError) as error:
        print("Couldn't assign bus to Child", error)

def confirm_payment(child_id):
    try:
        with awsconn, awsconn.cursor() as cur:
            cur.execute("UPDATE child SET payment_stat = %s WHERE id = %s", (True, child_id))
            awsconn.commit()

    except (Exception, psycopg2.DatabaseError) as error:
        print("Couldn't confirm payment", error)

def truncate_child_table():
    try:
        with awsconn, awsconn.cursor() as cur:
            # Retrieve the picture paths for each child before truncating the child table
            cur.execute("SELECT picture_path FROM child;")
            picture_paths = cur.fetchall()

            # Truncate the child table
            cur.execute("TRUNCATE TABLE child CASCADE;")  # The CASCADE option will also truncate related tables, if any.
            awsconn.commit()

            # Delete the pictures and their associated folders
            for picture in picture_paths:
                try:
                    picture_path = picture[0]
                    os.remove(picture_path)
                    folder_path = os.path.dirname(picture_path)
                    shutil.rmtree(folder_path)
                except OSError as e:
                    print(f"Error deleting picture or folder: {e}")

            print("Child table truncated successfully!")

    except (Exception, psycopg2.DatabaseError) as error:
        print("Could not truncate child table", error)


def get_bus_ID():
    try:
        with awsconn, awsconn.cursor() as cur:
            # Retrieve the picture paths for each child before truncating the child table
            cur.execute("SELECT id FROM bus")
            bus_ID = cur.fetchone()

            if bus_ID:
                id = bus_ID[0]
                return id
            

    except (Exception, psycopg2.DatabaseError) as error:
        print("Could not truncate child table", error)

