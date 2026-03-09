from flask import Flask, request, send_file, jsonify
import onnxruntime as ort
import numpy as np
from PIL import Image
import io
import urllib.request
import os

app = Flask(__name__, static_folder="static")

MODEL_PATH = os.path.join(os.path.dirname(__file__), "u2net.onnx")
MODEL_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx"

def download_model():
    if not os.path.exists(MODEL_PATH):
        print("Загвар татаж байна (u2net.onnx) ~170MB...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("Загвар татагдлаа.")

def preprocess(img: Image.Image):
    img = img.convert("RGB").resize((320, 320))
    arr = np.array(img, dtype=np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406])
    std  = np.array([0.229, 0.224, 0.225])
    arr = (arr - mean) / std
    arr = arr.transpose(2, 0, 1)[np.newaxis, ...]
    return arr.astype(np.float32)

def postprocess(mask: np.ndarray, orig_size):
    mask = mask.squeeze()
    mask = (mask - mask.min()) / (mask.max() - mask.min() + 1e-8)
    mask_img = Image.fromarray((mask * 255).astype(np.uint8)).resize(orig_size, Image.LANCZOS)
    return mask_img

# Load session once at startup
download_model()
session = ort.InferenceSession(MODEL_PATH, providers=["CPUExecutionProvider"])
input_name = session.get_inputs()[0].name

@app.route("/")
def index():
    return send_file("static/index.html")

@app.route("/remove-bg", methods=["POST"])
def remove_bg():
    if "image" not in request.files:
        return jsonify({"error": "Зураг илгээгдээгүй байна"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "Файл сонгогдоогүй байна"}), 400

    try:
        orig = Image.open(file.stream).convert("RGBA")
        orig_size = orig.size

        inp = preprocess(orig.convert("RGB"))
        preds = session.run(None, {input_name: inp})
        mask = postprocess(preds[0], orig_size)

        # Apply mask to alpha channel
        r, g, b, a = orig.split()
        orig.putalpha(mask)

        img_io = io.BytesIO()
        orig.save(img_io, format="PNG")
        img_io.seek(0)
        return send_file(img_io, mimetype="image/png")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=False, port=5051)
