from flask import Flask, request, jsonify
from zeroconf import Zeroconf, ServiceInfo
from ultralytics import YOLO
import socket
import requests
import os
import threading
import time
from datetime import datetime

# ============================================================
# CONFIGURATION
# ============================================================
PORT = 6000
SERVICE_TYPE = "_fog._tcp.local."
SERVICE_NAME = "FogNode2._fog._tcp.local."   # CHANGE for each slave node

# ⚠️ Replace with MASTER Hotspot IP (see ipconfig):
MASTER_URL = "http://192.168.137.1:8000/result"

UPLOAD_DIR = "received_images"
os.makedirs(UPLOAD_DIR, exist_ok=True)

available = 1   # 1 = ready, 0 = busy


# ============================================================
# LOAD YOLO MODEL
# ============================================================
print("[YOLO] Loading model...")
model = YOLO(r"bestNOW.pt")
print("[YOLO] Model loaded successfully!")


# ============================================================
# YOLO PROCESSING THREAD
# ============================================================
def process_image(image_path, frame_id):
    global available

    try:
        print(f"[PROCESS] Running YOLO on {image_path} (frame {frame_id})")

        start = time.time()
        results = model.predict(source=image_path, conf=0.5, show=False)
        duration = time.time() - start

        # Extract detections
        detections = []
        for box in results[0].boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            xyxy = box.xyxy[0].tolist()

            detections.append({
                "class": model.names[cls_id],
                "confidence": conf,
                "bbox": xyxy
            })

        # Build result payload
        result_payload = {
            "node": SERVICE_NAME,
            "frame_id": frame_id,
            "processing_time": duration,
            "detections": detections
        }

        # Send back to master
        try:
            requests.post(MASTER_URL, json=result_payload, timeout=1)
            print(f"[SEND] Sent result for frame {frame_id} back to master")

        except Exception as e:
            print(f"[ERROR] Failed sending results: {e}")

    except Exception as e:
        print(f"[ERROR] YOLO failed: {e}")

    # mark slave as free
    available = 1
    print("[STATUS] AVAILABLE again\n")


# ============================================================
# FLASK SERVER
# ============================================================
app = Flask(__name__)

@app.route("/status")
def status():
    """Master checks if node is free."""
    return jsonify({"available": available})


@app.route("/process", methods=["POST"])
def process():
    global available

    if available == 0:
        return jsonify({"status": "busy"}), 503

    if "image" not in request.files or "frame_id" not in request.form:
        return jsonify({"error": "Invalid request"}), 400

    # mark as busy
    available = 0
    print("[STATUS] BUSY")

    frame_id = int(request.form["frame_id"])

    # Save the image
    img = request.files["image"]
    filename = datetime.now().strftime("%Y%m%d_%H%M%S") + ".jpg"
    path = os.path.join(UPLOAD_DIR, filename)
    img.save(path)

    print(f"[SLAVE] Received frame {frame_id}, saved as {filename}")

    # Run YOLO asynchronously
    threading.Thread(
        target=process_image,
        args=(path, frame_id),
        daemon=True
    ).start()

    return jsonify({"status": "ok"})


# ============================================================
# mDNS REGISTRATION
# ============================================================
def register_mdns():
    ip = socket.gethostbyname(socket.gethostname())
    info = ServiceInfo(
        SERVICE_TYPE,
        SERVICE_NAME,
        addresses=[socket.inet_aton(ip)],
        port=PORT,
        properties={},
        server=f"{socket.gethostname()}.local.",
    )

    z = Zeroconf()
    z.register_service(info)
    print(f"[mDNS] Registered {SERVICE_NAME} at {ip}:{PORT}")
    return z


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    z = register_mdns()

    try:
        app.run(host="0.0.0.0", port=PORT)
    finally:
        z.unregister_all_services()
        z.close()