
## ⚡ Quick Setup

```bash
# Update your Pi first
sudo apt update && sudo apt upgrade -y

# Enable I2C and Camera
sudo raspi-config   # Interface Options → I2C → Enable
                    # Interface Options → Camera → Enable

# Core dependencies (all courses)
pip install RPi.GPIO board adafruit-blinka neopixel \
            adafruit-circuitpython-pca9685 adafruit-motor \
            opencv-python numpy

# Run hardware check
python utils.py
```

---

## 🧠 Course 1 — Mind-Controlled Robot Arm

```bash
pip install pyserial adafruit-circuitpython-pca9685 mindwave-python

# Pair your MindWave headset via Bluetooth, then:
sudo rfcomm connect 0 <HEADSET_BT_ADDRESS>

# Run demo (no headset needed)
python course1_mindarm/mind_arm_controller.py --demo

# Run with headset
python course1_mindarm/mind_arm_controller.py /dev/rfcomm0
```

---

## 💡 Tips for Students

- Always run `python utils.py` first to check your hardware is connected
- Use `--demo` flags where available to test without all hardware
- Each file has detailed comments explaining every concept
- The `utils.py` helpers (SmoothValue, RateLimiter, etc.) can be imported into any project

---

*Built with Python 3.11+ on Raspberry Pi OS (Bookworm)*
