import threading
import time
import requests
import os
import cv2
import base64

from flask import Flask, request, jsonify
from flask_cors import CORS

from zeroconf import Zeroconf, ServiceBrowser

# ======================================================================
# CONFIG
# ======================================================================
EXPECTED_NODES = ["FogNode1", "FogNode2", "FogNode3"]

DISCOVERED_NODES = []
results_buffer = {}
frames_buffer = {}            # frame_id → raw frame
frame_timestamps = {}         # frame_id → time_sent
FRAME_TIMEOUT = 1.0           # seconds

next_frame_to_print = 1
frame_id_counter = 1

last_result = None
last_frame_b64 = None

# NEW: used to measure frequency
results_received = 0          # <-- NEW

STATUS_PATH = "/status"

STREAM_URL = "http://esp32cam1.local/stream"
CAPTURE_INTERVAL = 0.01

# ======================================================================
# FLASK SERVER
# ======================================================================
app = Flask(__name__)
CORS(app)

@app.route("/nodes", methods=["GET"])
def get_nodes_status():
    nodes_info = []
    for name in EXPECTED_NODES:
        node_obj = next((n for n in DISCOVERED_NODES if n["name"] == name), None)
        if node_obj:
            base = node_obj["url"].rsplit("/", 1)[0]
            try:
                resp = requests.get(base + STATUS_PATH, timeout=0.4)
                available = resp.json().get("available")
            except:
                available = None
        else:
            available = None

        nodes_info.append({"name": name, "available": available})
    return jsonify(nodes_info)


@app.route("/last_result", methods=["GET"])
def last_result_route():
    if last_result is None:
        return jsonify({"message": "no result"})
    return jsonify(last_result)


@app.route("/last_frame", methods=["GET"])
def last_frame_route():
    if last_frame_b64 is None:
        return jsonify({"message": "no frame"})
    return jsonify({"image": last_frame_b64})

# ======================================================================
# YOLO RESULT RECEIVING
# ======================================================================
@app.route("/result", methods=["POST"])
def receive_result():
    global next_frame_to_print, last_result, last_frame_b64, results_received

    data = request.json
    frame_id = data["frame_id"]

    print(f"\n📥 Received result for frame {frame_id} from {data.get('node')}")

    results_buffer[frame_id] = data

    # ============================================================
    # ORDERED PRINTING WITH TIMEOUT SKIP
    # ============================================================
    while True:

        # ------------------------------------------------------------
        # 1️⃣ If we have the expected frame → print normally
        # ------------------------------------------------------------
        if next_frame_to_print in results_buffer:

            result = results_buffer.pop(next_frame_to_print)
            frame = frames_buffer.pop(next_frame_to_print, None)

            print("\n===================================")
            print(f"📥 ORDERED RESULT FOR FRAME {next_frame_to_print}")
            print(f"From: {result['node']}")
            print(f"Processing time: {result['processing_time']}")
            print("Detections:")
            for det in result["detections"]:
                print(f" • {det['class']} ({det['confidence']:.2f}) at {det['bbox']}")
            print("===================================\n")

            # 🔥 Count frequency of printed results
            results_received += 1  # <-- NEW

            last_result = result

            # Save annotated frame for front-end
            if frame is not None:
                annotated = draw_bboxes(frame, result["detections"])
                ok, enc = cv2.imencode(".jpg", annotated)
                if ok:
                    last_frame_b64 = base64.b64encode(enc).decode()

            next_frame_to_print += 1
            continue

        # ------------------------------------------------------------
        # 2️⃣ No result → check if this frame has timed out
        # ------------------------------------------------------------
        if next_frame_to_print in frame_timestamps:
            sent_at = frame_timestamps[next_frame_to_print]

            if time.time() - sent_at > FRAME_TIMEOUT:
                print(f"⏳ TIMEOUT — skipping frame {next_frame_to_print} (no response from fog node)")

                frames_buffer.pop(next_frame_to_print, None)
                results_buffer.pop(next_frame_to_print, None)
                frame_timestamps.pop(next_frame_to_print, None)

                next_frame_to_print += 1
                continue

        break  # nothing to print or skip yet

    return jsonify({"status": "ok"})

# ======================================================================
# BBOX DRAW FUNCTION
# ======================================================================
def draw_bboxes(frame, detections):
    img = frame.copy()
    for det in detections:
        x1, y1, x2, y2 = map(int, det["bbox"])
        cv2.rectangle(img, (x1, y1), (x2, y2), (255, 0, 0), 2)
        label = f"{det['class']} {det['confidence']:.2f}"
        cv2.putText(img, label, (x1, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (255, 0, 0), 2)
    return img

# ======================================================================
# SEND FRAME
# ======================================================================
def send_frame(frame, node, frame_id):
    success, encoded = cv2.imencode(".jpg", frame)
    if not success:
        print(f"❌ Encode error for frame {frame_id}")
        return

    try:
        resp = requests.post(
            node["url"],
            files={"image": ("frame.jpg", encoded.tobytes(), "image/jpeg")},
            data={"frame_id": frame_id},
            timeout=2
        )
        print(f"📤 Sent frame {frame_id} → {node['name']} ({resp.status_code})")
    except Exception as e:
        print(f"❌ Send error {node['name']}: {e}")

def check_node_status(node):
    base = node["url"].rsplit("/", 1)[0]
    try:
        r = requests.get(base + STATUS_PATH, timeout=0.4)
        return r.json().get("available")
    except:
        return None

# ======================================================================
# mDNS DISCOVERY
# ======================================================================
class FogServiceListener:
    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        if info:
            node_name = info.name.split("._fog")[0]
            ip = ".".join(map(str, info.addresses[0]))
            port = info.port
            url = f"http://{ip}:{port}/process"

            print(f"[mDNS] DETECTED fog node: {node_name} → {url}")

            if not any(n["name"] == node_name for n in DISCOVERED_NODES):
                DISCOVERED_NODES.append({"name": node_name, "url": url})
                print(f"[mDNS] REGISTERED fog node: {node_name}")

    def remove_service(self, zeroconf, type, name):
        node_name = name.split("._fog")[0]
        print(f"[mDNS] Fog node left: {node_name} (keeping in list)")

def start_mdns_monitor():
    print("[mDNS] Starting mDNS listener...")
    z = Zeroconf()
    listener = FogServiceListener()
    ServiceBrowser(z, "_fog._tcp.local.", listener)

# ======================================================================
# ESP32-CAM LOOP
# ======================================================================
def connect_stream():
    print(f"[INFO] Connecting to ESP32-CAM at {STREAM_URL} ...")
    cap = cv2.VideoCapture(STREAM_URL)
    for i in range(20):
        if cap.isOpened():
            print("[INFO] ESP32-CAM connected successfully.")
            return cap
        print("[WARN] Retry connecting to ESP32-CAM...")
        time.sleep(0.2)
    print("[ERROR] Failed to connect to ESP32-CAM.")
    return None

def camera_loop():
    global frame_id_counter

    while True:
        cap = connect_stream()
        if not cap:
            time.sleep(0.1)
            continue

        last_time = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                print("[WARN] Lost ESP32-CAM connection… Reconnecting…")
                break

            now = time.time()
            if now - last_time < CAPTURE_INTERVAL:
                continue
            last_time = now

            print("🎥 Captured new frame (not yet assigned id)")

            availability_line = []
            free_nodes = []

            for name in EXPECTED_NODES:
                node_obj = next((n for n in DISCOVERED_NODES if n["name"] == name), None)

                if node_obj is None:
                    availability_line.append(f"{name}: 🔵")
                    continue

                status = check_node_status(node_obj)

                if status == 1:
                    availability_line.append(f"{name}: 🟢")
                    free_nodes.append(node_obj)
                elif status == 0:
                    availability_line.append(f"{name}: 🔴")
                else:
                    availability_line.append(f"{name}: 🔵")

            print(" | ".join(availability_line))

            if not free_nodes:
                print("❌ No free fog nodes… frame dropped")
                continue

            free_nodes.sort(key=lambda n: int("".join(filter(str.isdigit, n["name"]))))

            target = free_nodes[0]

            frame_id = frame_id_counter
            frames_buffer[frame_id] = frame
            frame_timestamps[frame_id] = time.time()
            print(f"🆔 Assigned frame_id {frame_id} to this frame")
            frame_id_counter += 1

            send_frame(frame, target, frame_id)
            print(f"🎯 Frame {frame_id} dispatched to {target['name']}")

# ======================================================================
# FREQUENCY MONITOR THREAD
# ======================================================================
def frequency_monitor():         # <-- NEW
    global results_received
    last_count = 0

    while True:
        time.sleep(10)
        current = results_received
        fps = (current - last_count) / 10.0
        last_count = current

        print(f"⚡ RESULT FREQUENCY: {fps} FPS")  # <-- NEW


# ======================================================================
# MAIN
# ======================================================================
if __name__ == "__main__":
    print("🚀 Starting Fog Orchestrator...")

    # Flask server
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=8000, debug=False, use_reloader=False),
        daemon=True
    ).start()

    # mDNS listener
    threading.Thread(target=start_mdns_monitor, daemon=True).start()

    # 🔥 Start frequency monitor
    threading.Thread(target=frequency_monitor, daemon=True).start()   # <-- NEW

    print("[SYSTEM] Waiting 2 seconds for initial nodes...")
    time.sleep(2)

    print("🚀 Fog Orchestrator Running (ESP32-CAM → Fog Nodes)\n")
    camera_loop()
