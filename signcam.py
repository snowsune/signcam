import time
import argparse
import numpy as np
import cv2
import pyfakewebcam
import threading

from PIL import Image, ImageDraw, ImageFont

from pynput import keyboard
from pynput.keyboard import GlobalHotKeys


# --- Vixi Notes! ---
# You will need to
# sudo modprobe v4l2loopback devices=1 video_nr=10 card_label="VirtualCam" exclusive_caps=1
# Or similar first

# Things to do
# - Sound effects? :O
# - Fix it so i dont overflow the box >.<
# - Automated long-sentence readout
# - Is this actually a project i wanna do lol XD
# - Emoji support :P

# --- Hotkey to image map ---
hotkey_image_map = {
    "": "",
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

hotkey_image_map = [
    {
        "image": "images/blank.png",  # image location
        "bounds": [40, 370, 595, 450],  # like, where on the image you can draw text
        "keybind": "<alt>+0",
    },
    {
        "image": "images/yes.png",
        "keybind": "<alt>+1",
    },
    {
        "image": "images/no.png",
        "keybind": "<alt>+2",
    },
    {
        "image": "images/yay.png",
        "keybind": "<alt>+3",
    },
    {
        "image": "images/hi.png",
        "keybind": "<alt>+4",
    },
    {
        "image": "images/blep.png",
        "keybind": "<alt>+5",
    },
    {
        "image": "images/question.png",
        "keybind": "<alt>+6",
    },
]


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
# hotkey_actions = {
#     key: lambda p=path: set_overlay(p) for key, path in hotkey_image_map.items()
# }

hotkey_actions = {}

for item in hotkey_image_map:
    keybind = item["keybind"]
    path = item["image"]
    bounds = item.get("bounds")  # Can return like, nothing if .get fails

    def make_callback(path=path, bounds=bounds):
        def callback():
            global current_overlay
            img = load_overlay(path)

            if bounds:
                print(f"Enter to send in {bounds}:")
                while True:
                    user_text = input("> ").strip()
                    if not user_text:
                        print("Text input ended.")
                        break

                    # Get Bounds
                    x0, y0, x1, y1 = bounds

                    # PIL draw logic
                    pil_img = Image.open(path).convert("RGBA")
                    draw = ImageDraw.Draw(pil_img)
                    font = ImageFont.truetype(
                        "Action_Man.ttf",
                        (y1 - y0 + 20) / ((max(1, len(user_text) / 20) * 1.85)),
                    )

                    # Text Valid Area
                    text_area_w = x1 - x0
                    text_area_h = y1 - y0

                    # Box in text (required after pillow 10)
                    bbox = draw.textbbox((0, 0), user_text, font=font)
                    text_w = bbox[2] - bbox[0]
                    text_h = bbox[3] - bbox[1]
                    tx = x0 + (text_area_w - text_w) // 2
                    ty = y0 + (text_area_h - text_h) // 2

                    draw.text((tx, ty), user_text, font=font, fill=(0, 0, 0, 255))

                    # Convert back to OpenCV format
                    img_rgba = np.array(pil_img)
                    rgb_img = cv2.cvtColor(img_rgba, cv2.COLOR_RGBA2RGB)
                    img = rgb_img

                    # PUSH!
                    with overlay_lock:
                        current_overlay = img
                    camera.schedule_frame(img)  # Sends updated frame right now

                print(f"Switched to overlay: {path}")

        return callback

    hotkey_actions[keybind] = make_callback()


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
