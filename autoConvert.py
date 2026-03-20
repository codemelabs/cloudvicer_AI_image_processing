import os
import json
import numpy as np
import mysql.connector
from mysql.connector import pooling
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
from tensorflow.keras.preprocessing import image
from tensorflow.keras.models import Model
import logging

# ------------------ LOGGING ------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# ------------------ ENV CONFIG ------------------
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin")
DB_NAME = os.getenv("DB_NAME", "larapos")
DB_POOL_NAME = "mypool"
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", 5))

IMAGE_BASE_PATH = os.getenv(
    "IMAGE_BASE_PATH",
    r"D:\CSE\My Project\php\Laravel Poss\development v2\laravel_pos\public\img\products"
)

# ------------------ DATABASE CONNECTION POOL ------------------
db_pool = pooling.MySQLConnectionPool(
    pool_name="image_vector_pool",
    pool_size=DB_POOL_SIZE,
    pool_reset_session=True,
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME
)

# ------------------ LOAD MODEL ------------------
logging.info("Loading MobileNetV2 model...")
base_model = MobileNetV2(weights="imagenet", include_top=False, pooling="avg")
model = Model(inputs=base_model.input, outputs=base_model.output)
logging.info("Model loaded successfully.")

# ------------------ GET PRODUCTS ------------------
db = db_pool.get_connection()
cursor = db.cursor(dictionary=True)

cursor.execute("SELECT id, imgpath FROM products WHERE image_vector IS NULL")
products = cursor.fetchall()
logging.info(f"Total images to process: {len(products)}")

# ------------------ PROCESS IMAGES ------------------
for product in products:
    product_id = product["id"]
    imgpath = product["imgpath"]

    if not imgpath:
        logging.warning(f"Skipping product {product_id} because imgpath is NULL")
        continue

    filename = os.path.basename(imgpath)
    full_img_path = os.path.join(IMAGE_BASE_PATH, filename)

    if not os.path.exists(full_img_path):
        logging.warning(f"Image not found: {full_img_path}")
        continue

    try:
        # Load and preprocess image
        img = image.load_img(full_img_path, target_size=(224, 224))
        img_array = image.img_to_array(img)
        img_array = np.expand_dims(img_array, axis=0)
        img_array = preprocess_input(img_array)

        # Extract feature vector
        vector = model.predict(img_array, verbose=0)[0]
        vector_json = json.dumps(vector.tolist())

        # Update database
        update_query = "UPDATE products SET image_vector = %s WHERE id = %s"
        cursor.execute(update_query, (vector_json, product_id))
        db.commit()

        logging.info(f"Vector saved for product: {product_id}")

    except Exception as e:
        logging.error(f"Error processing {full_img_path}: {str(e)}")

cursor.close()
db.close()
logging.info("Finished processing all images.")