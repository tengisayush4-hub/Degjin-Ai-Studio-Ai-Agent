import os
import urllib.request
import ssl

# Reliable mirror for u2net.onnx
MODEL_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx"
TARGET_DIR = os.path.join(os.path.dirname(__file__), "bg_remover")
TARGET_PATH = os.path.join(TARGET_DIR, "u2net.onnx")

def download_model():
    if not os.path.exists(TARGET_DIR):
        os.makedirs(TARGET_DIR)
        
    if os.path.exists(TARGET_PATH):
        print(f"Model already exists at {TARGET_PATH}")
        return

    print(f"Downloading u2net.onnx from {MODEL_URL}...")
    
    # Bypass SSL verification for older Python / Render environment compatibility
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        with urllib.request.urlopen(MODEL_URL, context=ctx) as response, open(TARGET_PATH, 'wb') as out_file:
            data = response.read()
            out_file.write(data)
        print("Download complete!")
    except Exception as e:
        print(f"Failed to download model: {e}")
        raise

if __name__ == "__main__":
    download_model()
