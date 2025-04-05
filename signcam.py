import time
import argparse
import numpy as np
import cv2
import pyfakewebcam
import threading

from pynput import keyboard
from pynput.keyboard import GlobalHotKeys


# --- Vixi Notes! ---
# You will need to
# sudo modprobe v4l2loopback devices=1 video_nr=10 card_label="VirtualCam" exclusive_caps=1
# Or similar first

# --- Hotkey to image map ---
hotkey_image_map = {
    "<alt>+0": "images/blank.png",
    "<alt>+1": "images/yes.png",
    "<alt>+2": "images/no.png",
    "<alt>+3": "images/yay.png",
    "<alt>+4": "images/hi.png",
    "<alt>+5": "images/blep.png",
    "<alt>+6": "images/question.png",
    "<alt>+7": "images/vixi-sticker-sparkle-ver2.png",
}


# Mmhh.... better idea
# Composite map like...

better_map = [
    {
        "image": "path/to/image",  # image location
        "bounds": [0, 0, 100, 100],  # like, where on the image you can draw text
        "keybind": "<alt>+X",
    },
    {
        "image": "path/to/image",
        "bounds": [0, 0, 100, 100],
        "keybind": "<alt>+X",
    },
]

# Is better ideear
# So like, use pillow to draw on?
# Beep boop it doo~
# Ima make a ?? emoji one sec


# --- Args ---
parser = argparse.ArgumentParser(
    description="Vixi's Virtual Camera Driver (with optional bg compositor)"
)
parser.add_argument("--device", default="/dev/video10", help="v4l2loopback device path")
parser.add_argument("--width", type=int, default=640, help="Frame width")
parser.add_argument("--height", type=int, default=480, help="Frame height")
parser.add_argument(
    "--bg", type=str, default="0,0,0", help="Background color (R,G,B)"
)  # 0,255,0 for OBS

args = parser.parse_args()
bg_color = tuple(map(int, args.bg.split(",")))

# --- Virtual camera setup ---
camera = pyfakewebcam.FakeWebcam(args.device, args.width, args.height)
current_overlay = None
overlay_lock = threading.Lock()


# --- Image loading ---
def load_overlay(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        print(f"Warning: couldn't load {path}")
        return None

    # Resize to fit
    img = cv2.resize(img, (args.width, args.height))

    # Convert to 3-channel RGB if no alpha
    if img.shape[2] == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    elif img.shape[2] == 4:
        # Convert with alpha blending
        b, g, r, a = cv2.split(img)
        alpha = a.astype(np.float32) / 255.0
        rgb = cv2.merge([r, g, b])
        background = np.full_like(rgb, bg_color, dtype=np.uint8)
        blended = (alpha[..., None] * rgb + (1 - alpha[..., None]) * background).astype(
            np.uint8
        )
        return blended
    else:
        print(f"Unsupported image format: {path}")
        return None


# --- Hotkey callbacks ---
def set_overlay(path):
    global current_overlay
    new_overlay = load_overlay(path)

    # Draw in here
    # Pillow, composite on thingy

    with overlay_lock:
        current_overlay = new_overlay
    print(f"Switched to overlay: {path}")


# --- Register hotkeys ---
hotkey_actions = {
    key: lambda p=path: set_overlay(p) for key, path in hotkey_image_map.items()
}


def start_hotkey_listener():
    with GlobalHotKeys(hotkey_actions) as h:
        h.join()


listener_thread = threading.Thread(target=start_hotkey_listener, daemon=True)
listener_thread.start()

# --- Main loop ---
print("Streaming to virtual camera. Press your hotkeys to switch overlays.")
frame_bg = np.full((args.height, args.width, 3), bg_color, dtype=np.uint8)

while True:
    with overlay_lock:
        if current_overlay is not None:
            frame = current_overlay.copy()
        else:
            frame = frame_bg.copy()

    camera.schedule_frame(frame)
    time.sleep(1 / 24)
