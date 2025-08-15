from flask import Flask, request, jsonify
import threading, time, os, wave, numpy as np
from openal import oalInit, oalQuit, oalOpen, Listener

# --- Config ---
HOST = "10.241.7.52"   # use "0.0.0.0" to accept from LAN
PORT = 8081
BEEP_PATH = "beep-08b.wav"
GAIN = 0.8
USE_X_FORWARD_FRAME = True  # True if your coords are X-forward
COLLISION_TTL = 2        # seconds without updates => auto-clear
# --- Audio update control ---
MIN_UPDATE_PERIOD = 0.033   # ~30 Hz max source updates
POS_ALPHA = 0.35            # 0..1 low-pass smoothing for position
_last_move = 0.0
_last_pos = np.array([0.0, 0.0, 0.0], dtype=float)

# Force OpenAL Soft HRTF for better 3D
os.environ.setdefault("ALSOFT_HRTF", "1")

app = Flask(__name__)

# --- Shared state (guarded by _state_lock) ---
_latest = {
    "state": "none",       # "contact" | "none"
    "hit": False,          # kept for backward-compat GET /collision
    "nearest": None,       # {"x":..,"y":..,"z":..} or None
    "frame": "camera_link",
    "stamp": 0.0,
    "_received_at": 0.0
}
_state_lock = threading.Lock()
_is_playing = False  # guarded by _state_lock

# --- Make a short beep if not present ---
def ensure_beep(path=BEEP_PATH, dur=0.15, sr=44100, freq=880.0):
    if os.path.exists(path):
        return
    t = np.linspace(0, dur, int(sr*dur), endpoint=False)
    env = np.exp(-8*t)  # short plucky envelope
    y = (0.5*np.sin(2*np.pi*freq*t) * env).astype(np.float32)
    y16 = (y * 32767).astype(np.int16).tobytes()
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(y16)

ensure_beep()

def _set_source_position(x, y, z):
    global _last_move, _last_pos
    now = time.time()
    # Rate limit
    if (now - _last_move) < MIN_UPDATE_PERIOD:
        return
    # Low-pass smoothing to avoid jitter-buzz
    target = np.array([x, y, z], dtype=float)
    smoothed = POS_ALPHA * target + (1.0 - POS_ALPHA) * _last_pos
    src.set_position(tuple(smoothed))
    _last_pos = smoothed
    _last_move = now

# --- OpenAL init ---
oalInit()
listener = Listener()
listener.set_position([0, 0, 0])
listener.set_orientation([1, 0, 0,  0, 0, 1])   # at, up

src = oalOpen(BEEP_PATH)
src.set_looping(True)
src.set_gain(GAIN)
src.pause()  # start paused

def map_coords(x, y, z):
    """
    Map incoming camera coords to audio coords.
    If your camera is optical Z-forward, set USE_X_FORWARD_FRAME=False:
      camera_optical (x=right, y=down, z=fwd) -> audio (+X fwd, +Z up):
      return (z, -x, -y)
    """
    if USE_X_FORWARD_FRAME:
        return (float(x), float(y), float(z))
    else:
        return (float(z), float(-x), float(-y))

def _apply_state_contact(nearest_xyz, frame="camera_link", ts=None):
    """Apply CONTACT: move source, play if not playing."""
    global _is_playing
    now = time.time() if ts is None else float(ts)
    x, y, z = map_coords(nearest_xyz["x"], nearest_xyz["y"], nearest_xyz["z"])
    with _state_lock:
        _set_source_position(x, y, z)  # debounced + smoothed
        if _latest["state"] != "contact" or not _is_playing:
            src.play()
            _is_playing = True
        _latest.update({
            "state": "contact",
            "hit": True,
            "nearest": {"x": nearest_xyz["x"], "y": nearest_xyz["y"], "z": nearest_xyz["z"]},
            "frame": frame,
            "stamp": now,
            "_received_at": time.time()
        })
        _maybe_log_state_change()  # <---- log sur changement d'état

def _apply_state_none(ts=None):
    """Apply NONE: pause sound if playing and clear nearest."""
    global _is_playing
    now = time.time() if ts is None else float(ts)
    with _state_lock:
        if _is_playing:
            src.pause()
            _is_playing = False
        _latest.update({
            "state": "none",
            "hit": False,
            "nearest": None,
            "stamp": now,
            "_received_at": time.time()
        })
        _maybe_log_state_change()  # <---- log sur changement d'état

# --- New API: explicit 'contact' / 'none' ---
@app.post("/collision_event")
def collision_event():
    data = request.get_json(force=True)
    typ = data.get("type")
    ts = data.get("ts", None)

    if typ == "contact":
        contacts = data.get("contacts", [])
        if not contacts:
            _apply_state_none(ts)
            return jsonify({"ok": True, "note": "empty contacts -> none"})
        first = contacts[0]
        pos = first.get("pos") or first.get("position")
        if not pos or len(pos) != 3:
            return jsonify({"ok": False, "error": "contact missing pos [x,y,z]"}), 400
        nearest = {"x": float(pos[0]), "y": float(pos[1]), "z": float(pos[2])}
        frame = first.get("frame", "camera_link")
        _apply_state_contact(nearest, frame, ts)
        return jsonify({"ok": True})

    elif typ == "none":
        _apply_state_none(ts)
        return jsonify({"ok": True})

    return jsonify({"ok": False, "error": "unknown type"}), 400

# --- Backward-compatible API (your current publisher) ---
# Expects: {"hit": bool, "nearest": {"x":..,"y":..,"z":..}, "frame": "...", "stamp": ...}
@app.post("/collision")
def collision_post():
    data = request.get_json(force=True)
    hit = bool(data.get("hit", False))
    nearest = data.get("nearest")
    frame = data.get("frame", "camera_link")
    ts = data.get("stamp", None)

    if hit and nearest:
        _apply_state_contact(
            {"x": float(nearest["x"]), "y": float(nearest["y"]), "z": float(nearest["z"])},
            frame, ts
        )
    else:
        _apply_state_none(ts)
    return jsonify({"ok": True})

# --- Query current state ---
@app.get("/collision_state")
def collision_state():
    with _state_lock:
        # Return minimal, explicit state
        return jsonify({
            "state": _latest["state"],
            "hit": _latest["hit"],
            "nearest": _latest["nearest"],
            "frame": _latest["frame"],
            "stamp": _latest["stamp"],
            "age": time.time() - _latest["_received_at"]
        })

@app.get("/test")
def test():
    # quick sanity: put sound 0.8m ahead, 0.3m left, 0.0m up (in +X forward frame)
    x, y, z = map_coords(0.8, 0.3, 0.0)
    with _state_lock:
        src.set_position((x, y, z))
        src.play()
        global _is_playing
        _is_playing = True
    return jsonify({"ok": True, "pos": [x, y, z]})

# --- Watchdog: auto-clear after TTL so contacts never stick ---
def _watchdog():
    global _is_playing
    while True:
        time.sleep(0.1)
        now = time.time()
        with _state_lock:
            age = now - _latest["_received_at"]
            if _latest["state"] == "contact" and age > COLLISION_TTL:
                # No updates recently -> clear to "none"
                if _is_playing:
                    src.pause()
                    _is_playing = False
                _latest.update({
                    "state": "none",
                    "hit": False,
                    "nearest": None,
                    "stamp": now,
                    "_received_at": now
                })


@app.post("/silence")
def silence():
    global _is_playing
    with _state_lock:
        if _is_playing:
            src.pause()
            _is_playing = False
        _latest.update({
            "state": "none",
            "hit": False,
            "nearest": None,
            "stamp": time.time(),
            "_received_at": time.time()
        })
        _maybe_log_state_change()
    return jsonify({"ok": True, "note": "silenced"})

_last_reported_state = None
def _maybe_log_state_change():
    global _last_reported_state
    if _latest["state"] != _last_reported_state:
        print(f"[AUDIO] State -> { _latest['state'] } | playing={_is_playing} | nearest={_latest['nearest']}")
        _last_reported_state = _latest["state"]



def main():
    try:
        threading.Thread(target=_watchdog, daemon=True).start()
        app.run(host=HOST, port=PORT, threaded=True)
    finally:
        try:
            src.stop()
        finally:
            oalQuit()

if __name__ == "__main__":
    main()
