🚀 Fog Computing Vision Orchestrator
Distributed Real-Time Object Detection Using ESP32-CAM + Fog Nodes + React Dashboard

This project implements a real-time distributed computer vision system based on Fog Computing.
Instead of sending all raw camera frames to the cloud, an ESP32-CAM streams images to a Master Orchestrator, which distributes frames across multiple Fog Nodes.
Each Fog Node performs YOLO object detection, returns the result to the Master, which orders the frames, draws bounding boxes, and streams annotated frames to a React dashboard.

📌 Features
🖼️ Real-Time Video Inference

ESP32-CAM streams frames to the Master

Master sends frames to Fog Nodes

YOLO detection runs at the edge, not in the cloud

Front-end receives annotated frames in real time

☁️ Fog-Based Distributed Processing

Fog Nodes are auto-discovered using mDNS (zeroconf)

Only available nodes receive frames

Frames are always processed in correct order (1,2,3...)

Master avoids dropped frame IDs when nodes are busy

🧠 Smart Ordering System

Fog Nodes return results asynchronously → order is unpredictable:
The Master uses a results_buffer to reorder frames before sending them to the dashboard.

🖥️ Beautiful Real-Time Dashboard (React)

Live video feed (annotated)

Real-time detection results

Node status indicator (🟢 available / 🔴 busy / 🔵 unreachable)

Friendly message when no detections → “Aucune détection”

🔀 Fault Tolerance

If no fog node is free → frame skipped safely

No increment of frame_id when frame is not dispatched