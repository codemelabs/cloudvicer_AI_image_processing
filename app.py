import os
import json
import base64
import traceback
from io import BytesIO

from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
from mysql.connector import pooling

from feature_extractor import extract_vector
from similarity import find_similar


app = Flask(__name__)
CORS(app)
app.config['PROPAGATE_EXCEPTIONS'] = True
app.config['DEBUG'] = False 

# --- Environment Variables ---
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin")
DB_NAME = os.getenv("DB_NAME", "larapos")
DB_POOL_NAME = "mypool"
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", 5))

# --- Database Connection Pool ---
db_pool = pooling.MySQLConnectionPool(
    pool_name=DB_POOL_NAME,
    pool_size=DB_POOL_SIZE,
    pool_reset_session=True,
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME
)

def get_db():
    return db_pool.get_connection()


# --- Routes ---
@app.route("/save-image-vector", methods=["POST"])
def save_image_vector():
    try:
        data = request.get_json()
        product_id = data.get("product_id")
        image_base64 = data.get("image_base64")

        if not product_id or not image_base64:
            return jsonify({"error": "product_id and image_base64 are required"}), 400

        image_bytes = base64.b64decode(image_base64)
        image_io = BytesIO(image_bytes)
        vector = extract_vector(image_io)

        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "UPDATE products SET image_vector = %s WHERE id = %s",
            (json.dumps(vector), product_id)
        )
        db.commit()
        cursor.close()
        db.close()

        return jsonify({"message": "Image vector saved successfully", "product_id": product_id}), 200

    except Exception as e:
        app.logger.error(f"save_image_vector ERROR: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/search_by_image", methods=["POST"])
def search_by_image():
    try:
        query_image = request.files.get("image")
        if query_image is None:
            return jsonify({"error": "No image provided"}), 400

        query_path = "query.jpg"
        query_image.save(query_path)
        query_vector = extract_vector(query_path)

        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, name, imgpath, total_stock, image_vector
            FROM products
            WHERE image_vector IS NOT NULL
        """)
        products = cursor.fetchall()
        if not products:
            return jsonify({"error": "No indexed products found"}), 404

        product_vectors = [json.loads(p["image_vector"]) for p in products]
        results = find_similar(query_vector, product_vectors)
        results = results[:1]  # Take top match

        response = []
        for index, score in results:
            prod = products[index]

            batch_cursor = db.cursor(dictionary=True)
            batch_cursor.execute("""
                SELECT batch_id, selling_price, COUNT(id) AS count
                FROM product_details
                WHERE product_id = %s
                GROUP BY batch_id, selling_price
            """, (prod["id"],))
            batches = batch_cursor.fetchall()
            batch_cursor.close()

            response.append({
                "product_id": prod["id"],
                "name": prod["name"],
                "imgpath": prod["imgpath"],
                "stock": float(prod["total_stock"]),
                "similarity": float(score),
                "batches": batches
            })

        cursor.close()
        db.close()
        return jsonify(response)

    except Exception as e:
        app.logger.error(f"search_by_image ERROR: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/search_by_image_customer", methods=["POST"])
def search_by_image_customer():
    try:
        query_image = request.files.get("image")
        if query_image is None:
            return jsonify({"error": "No image provided"}), 400

        query_path = "query.jpg"
        query_image.save(query_path)
        query_vector = extract_vector(query_path)

        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, name, imgpath, image_vector
            FROM products
            WHERE image_vector IS NOT NULL
        """)
        products = cursor.fetchall()
        if not products:
            return jsonify({"error": "No indexed products found"}), 404

        product_vectors = [json.loads(p["image_vector"]) for p in products]
        results = find_similar(query_vector, product_vectors)
        if not results:
            return jsonify({"error": "No similar products found"}), 404

        top_index, score = results[0]
        prod = products[top_index]

        batch_cursor = db.cursor(dictionary=True)
        batch_cursor.execute("""
            SELECT batch_id, selling_price, COUNT(id) AS in_stock
            FROM product_details
            WHERE product_id = %s
            GROUP BY batch_id, selling_price
            HAVING in_stock > 0
            ORDER BY selling_price DESC
            LIMIT 1
        """, (prod["id"],))
        batch = batch_cursor.fetchone()
        batch_cursor.close()
        cursor.close()
        db.close()

        if batch:
            response = {
                "product_id": prod["id"],
                "name": prod["name"],
                "imgpath": prod["imgpath"],
                "in_stock": int(batch["in_stock"]),
                "price": float(batch["selling_price"]),
                "similarity": float(score)
            }
        else:
            response = {
                "product_id": prod["id"],
                "name": prod["name"],
                "imgpath": prod["imgpath"],
                "in_stock": 0,
                "price": None,
                "similarity": float(score),
                "out_of_stock": True
            }

        return jsonify(response)

    except Exception as e:
        app.logger.error(f"search_by_image_customer ERROR: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5001))
    app.run(host="0.0.0.0", port=port)