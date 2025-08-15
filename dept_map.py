import serial, threading, time, cv2
from collections import deque
from flask import Flask, Response, stream_with_context, jsonify
import numpy as np
from PIL import Image
from qai_hub_models.models.depth_anything_v2.model import DepthAnythingV2
from qai_hub_models.models._shared.depth_estimation.app import DepthEstimationApp
from qai_hub_models.utils.onnx_torch_wrapper import OnnxModelTorchWrapper
import json

# --- Paramètres --- #
MODEL_PATH = r"C:\Users\arint\Documents\depth\distance-estimation-tool\depth_anything_v2.onnx"
IMU_PORT = 'COM3'
IMU_BAUDRATE = 115200
MIN_DIST = 1.0
MAX_DIST =5.0
SLEEP_TIME = 1/30  # 30 FPS
# --- IMU --- #
imu_ser = serial.Serial(IMU_PORT, IMU_BAUDRATE, timeout=0.01)
imu_buffer = deque(maxlen=2000)


# Stockage buffers IMU par timestamp (associés aux images)
synced_imu = deque(maxlen=100)  # [(timestamp, [imu_measurements])]

imu_lock = threading.Lock()

def imu_reader():
    imu_start_us = None
    system_monotonic_start = time.monotonic()
    unix_start_time = time.time()

    while True:
        try:
            line = imu_ser.readline().decode('utf-8', errors='ignore').strip()
            parts = line.split(' ')
            if len(parts) == 7:
                ts_raw = float(parts[0])  # en microsecondes
                vals = tuple(map(float, parts[1:]))

                if imu_start_us is None:
                    imu_start_us = ts_raw
                    

                # ➤ Convert microseconds → seconds
                delta_sec = (ts_raw - imu_start_us) / 1_000_000.0
                ts_unix = unix_start_time + delta_sec

                

                with imu_lock:
                    imu_buffer.append((ts_unix, *vals))

        except Exception as e:
            print("Erreur IMU:", e)


threading.Thread(target=imu_reader, daemon=True).start()

# --- Modèle --- #
depth_app = DepthEstimationApp(model=OnnxModelTorchWrapper.OnNPU(MODEL_PATH),
                               input_height=518, input_width=518)

# --- Caméra --- #
cap = cv2.VideoCapture(1)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 800)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 600)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))

# --- Conversion profondeur --- #
def depth_to_distance(depth_map, min_dist=MIN_DIST, max_dist=MAX_DIST):
    depth_norm = (depth_map - depth_map.min()) / (depth_map.max() - depth_map.min() + 1e-8)
    return min_dist + (1.0 - depth_norm) * (max_dist - min_dist)

# --- Variables globales pour Flask --- #
latest_rgb = None
latest_depth = None
latest_imu_buffer = []

# --- Traitement vidéo / profondeur --- #
# --- Global tracker for last IMU sample used --- #
last_imu_ts = 0.0  # global, initialized once at top

def camera_loop():
    global latest_rgb, latest_depth, latest_imu_buffer, last_imu_ts, latest_depth_float 
    while True:
        ret, frame = cap.read()
        if not ret:
            continue     
        # RGB to depth
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb).resize((518, 518), Image.BILINEAR)
        depth_map = depth_app.estimate_depth(img, raw_output=True)
        dist = depth_to_distance(depth_map)
        latest_depth_float = dist.copy()

        # Visualize
        _, rb = cv2.imencode('.jpg', frame)
        latest_rgb = rb.tobytes()

        # Timestamp image
        timestamp = time.time()

        # Synchronisation IMU
        with imu_lock:
            imu_list = list(imu_buffer)

        # Garder les mesures < timestamp de l’image, dans les 1s précédentes
        synced = [sample for sample in imu_list if 0 < timestamp - sample[0] < 1.0]

        # Mise à jour des buffers globaux
        latest_imu_buffer = synced
        synced_imu.append((timestamp, synced))
        last_imu_ts = timestamp  # pour suivi

        time.sleep(SLEEP_TIME)


threading.Thread(target=camera_loop, daemon=True).start()

# --- Serveur Flask --- #
app = Flask(__name__)
# --- Add at top-level globals ---
latest_depth_float = None  # ensure defined before first use

@app.route('/frame_rgb')
def frame_rgb():
    # Returns one JPEG frame
    if latest_rgb is None:
        return Response(status=503)
    return Response(latest_rgb, mimetype='image/jpeg')

@app.route('/frame_depth_raw')
def frame_depth_raw():
    # Returns one 16-bit PNG (uint16 millimeters)
    if latest_depth_float is None:
        return Response(status=503)
    depth_16 = (latest_depth_float * 1000.0).astype(np.uint16)  # meters -> mm
    ok, png = cv2.imencode('.png', depth_16)
    if not ok:
        return Response(status=500)
    return Response(png.tobytes(), mimetype='image/png')


@app.route('/imu_buffer')
def imu_buffer_stream():
    if synced_imu:
        current_ts, imu_data = synced_imu[-1]
        imu_list = [
            {
                "ts": ts,
                "ax": ax, "ay": ay, "az": az,
                "gx": gx, "gy": gy, "gz": gz
            }
            for ts, ax, ay, az, gx, gy, gz in imu_data  # <- use the synced imu only
        ]
        imu_json = {
            "timestamp": current_ts,
            "imu": imu_list
        }
        return jsonify(imu_json)
    else:
        return jsonify({"timestamp": None, "imu": []})

@app.route('/imu_raw')
def imu_raw():
    with imu_lock:
        imu_list = [
            {
                "ts": ts,
                "ax": ax, "ay": ay, "az": az,
                "gx": gx, "gy": gy, "gz": gz
            }
            for ts, ax, ay, az, gx, gy, gz in imu_buffer
        ]
    return jsonify({"imu": imu_list})


# --- Démarrage --- #
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, threaded=True)
