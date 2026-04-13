import os
import re
import io
import traceback
import pdfplumber
import requests
from flask import Flask, request, jsonify, send_file
from functools import wraps
from PIL import Image

# Initialize Flask App
app = Flask(__name__)

# Security: Basic API Key protection
# In Render, set this as an Environment Variable named 'AI_API_KEY'
API_KEY = os.environ.get('AI_API_KEY', 'meesho_secret_token_change_me')

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.headers.get('X-API-Key') != API_KEY:
            return jsonify({"status": "error", "message": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function

# --- Route: Order PDF Parser (Meesho) ---
@app.route('/parse_meesho_label', methods=['POST'])
@require_api_key
def parse_meesho_label():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file"}), 400
    file = request.files['file']
    try:
        orders = []
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text: continue
                
                # Logic from original label_parser_server.py
                po_match = re.search(r'([0-9]+)\s+([a-zA-Z0-9]+)\s+([0-9]{2}\.[0-9]{2}\.[0-9]{4})\s+([0-9]{2}\.[0-9]{2}\.[0-9]{4})', text)
                order_id = po_match.group(1) if po_match else None
                date = po_match.group(3) if po_match else None
                
                awb = None
                text_before_product = text.split('Product Details')[0] if 'Product Details' in text else text
                awb_matches = re.findall(r'\b([A-Z]{2}[0-9]{8,20}|[0-9]{12,25})\b', text_before_product)
                if awb_matches: awb = awb_matches[-1]

                customer_name = ""
                lines = text.split('\n')
                found_customer = False
                for line in lines:
                    if "Customer Address" in line: found_customer = True; continue
                    if found_customer and not customer_name: customer_name = line.strip(); break

                if order_id or awb:
                    orders.append({
                        "order_id": order_id,
                        "awb_number": awb,
                        "order_date": date,
                        "customer_name": customer_name,
                        "status": "Order Received"
                    })
        return jsonify({"status": "success", "orders": orders}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Route: Image Conversion (Pillow) ---
@app.route('/convert', methods=['POST'])
@require_api_key
def convert_image():
    if 'image' not in request.files:
        return jsonify({"error": "No image"}), 400
    
    file = request.files['image']
    output_format = request.form.get('output_format', 'webp').lower()
    if output_format == 'jpg': output_format = 'jpeg'

    try:
        img = Image.open(file.stream)
        if img.mode in ("RGBA", "P") and output_format == "jpeg":
            img = img.convert("RGB")
        
        img_out = io.BytesIO()
        img.save(img_out, format=output_format)
        img_out.seek(0)
        return send_file(img_out, mimetype=f'image/{output_format}')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Route: Shipping Scraper (Meesho) ---
@app.route('/calculate', methods=['POST'])
@require_api_key
def calculate_shipping():
    data = request.json
    weight = data.get('weight', 500)
    # Placeholder for scraping logic (requires Playwright, usually too heavy for free Render)
    # Returning a mock success for now
    return jsonify({
        "status": "success",
        "data": {
            "provider": "Delhivery (Auto)",
            "zone": "National",
            "base_rate": 65.0,
            "gst": 11.7,
            "total": 76.7,
            "reverse": 45.0
        }
    }), 200

# --- Route: Health Check ---
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "online", "version": "1.0.0"}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
