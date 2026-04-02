"""
╔══════════════════════════════════════════════════════════════════╗
║   COURSE 1: MIND-CONTROLLED ROBOT ARM                            ║
║   mind_arm_controller.py — Main Controller                       ║
║                                                                  ║
║   Hardware: Raspberry Pi 4, NeuroSky MindWave Mobile 2,          ║
║             PCA9685 PWM Driver, MG996R Servos x4                 ║
║                                                                  ║
║   pip install pyserial adafruit-circuitpython-pca9685            ║
║               adafruit-blinka mindwave-python                    ║
╚══════════════════════════════════════════════════════════════════╝
"""

import time
import threading
import collections
import board
import busio
from adafruit_pca9685 import PCA9685
from adafruit_motor import servo as adafruit_servo
import mindwave  # NeuroSky MindWave library

# ─────────────────────────────────────────────
#  SERVO CONFIGURATION
#  Adjust MIN/MAX pulse widths for your servos
# ─────────────────────────────────────────────
SERVO_CONFIG = {
    "base":    {"channel": 0, "min_angle": 0,  "max_angle": 180, "default": 90},
    "shoulder":{"channel": 1, "min_angle": 20, "max_angle": 160, "default": 90},
    "elbow":   {"channel": 2, "min_angle": 30, "max_angle": 150, "default": 90},
    "gripper": {"channel": 3, "min_angle": 0,  "max_angle": 60,  "default": 0},
}

# ─────────────────────────────────────────────
#  BRAINWAVE THRESHOLDS  (tune to your headset)
# ─────────────────────────────────────────────
ATTENTION_GRIP_THRESHOLD   = 60    # Focus score (0-100) to close gripper
ATTENTION_LIFT_THRESHOLD   = 80    # High focus lifts the shoulder
BLINK_ROTATE_THRESHOLD     = 150   # Blink strength to rotate base
SMOOTHING_WINDOW           = 5     # Rolling average window size

# ─────────────────────────────────────────────
#  SHARED STATE — thread-safe via threading.Lock
# ─────────────────────────────────────────────
brain_state = {
    "attention":  0,
    "meditation": 0,
    "blink":      0,
    "signal_quality": 200,  # 0 = best, 200 = no signal
}
state_lock = threading.Lock()
running = True

# Rolling average buffers
attention_buffer  = collections.deque(maxlen=SMOOTHING_WINDOW)
meditation_buffer = collections.deque(maxlen=SMOOTHING_WINDOW)


# ═══════════════════════════════════════════════════════════════════
#  SERVO MANAGER
# ═══════════════════════════════════════════════════════════════════
class ArmController:
    """Controls all four servo joints of the robotic arm."""

    def __init__(self):
        # Initialise I2C and PCA9685
        i2c = busio.I2C(board.SCL, board.SDA)
        self.pca = PCA9685(i2c)
        self.pca.frequency = 50  # Standard 50Hz for servos

        # Create servo objects for each joint
        self.servos = {}
        for name, cfg in SERVO_CONFIG.items():
            self.servos[name] = adafruit_servo.Servo(
                self.pca.channels[cfg["channel"]],
                min_pulse=500, max_pulse=2500
            )
        self.reset_position()
        print("[ARM] Servo controller initialised ✓")

    def set_angle(self, joint: str, angle: float, speed_delay: float = 0.01):
        """Smoothly move a joint to a target angle."""
        cfg = SERVO_CONFIG[joint]
        # Clamp to safe range
        angle = max(cfg["min_angle"], min(cfg["max_angle"], angle))
        current = self.servos[joint].angle or cfg["default"]

        # Step towards target (smooth movement)
        step = 1 if angle > current else -1
        for pos in range(int(current), int(angle), step):
            self.servos[joint].angle = pos
            time.sleep(speed_delay)
        self.servos[joint].angle = angle

    def reset_position(self):
        """Move all joints to their default/home position."""
        print("[ARM] Moving to home position...")
        for name, cfg in SERVO_CONFIG.items():
            self.servos[name].angle = cfg["default"]
        time.sleep(1)

    def grip(self, close: bool):
        """Open or close the gripper."""
        angle = SERVO_CONFIG["gripper"]["max_angle"] if close else 0
        self.set_angle("gripper", angle, speed_delay=0.008)

    def lift(self, level: float):
        """Lift shoulder. level = 0.0 (down) to 1.0 (up)."""
        cfg = SERVO_CONFIG["shoulder"]
        angle = cfg["min_angle"] + (cfg["max_angle"] - cfg["min_angle"]) * level
        self.set_angle("shoulder", angle)

    def rotate_base(self, direction: str):
        """Rotate base left or right by 30 degrees."""
        current = self.servos["base"].angle or 90
        delta = 30 if direction == "right" else -30
        self.set_angle("base", current + delta)

    def cleanup(self):
        self.reset_position()
        self.pca.deinit()


# ═══════════════════════════════════════════════════════════════════
#  MINDWAVE READER THREAD
# ═══════════════════════════════════════════════════════════════════
def mindwave_thread(headset_address: str):
    """
    Connects to NeuroSky MindWave via Bluetooth serial.
    Updates brain_state dict continuously.

    headset_address: Bluetooth serial port, e.g. '/dev/rfcomm0'
    Run first: sudo rfcomm connect 0 <HEADSET_BT_ADDRESS>
    """
    global running
    headset = mindwave.Headset(headset_address)
    print(f"[BRAIN] Connecting to MindWave at {headset_address}...")

    @headset.on('attention')
    def on_attention(headset, value):
        with state_lock:
            attention_buffer.append(value)
            brain_state["attention"] = int(sum(attention_buffer) / len(attention_buffer))

    @headset.on('meditation')
    def on_meditation(headset, value):
        with state_lock:
            meditation_buffer.append(value)
            brain_state["meditation"] = int(sum(meditation_buffer) / len(meditation_buffer))

    @headset.on('blink')
    def on_blink(headset, value):
        with state_lock:
            brain_state["blink"] = value
        print(f"[BRAIN] Blink detected — strength: {value}")

    @headset.on('poor_signal')
    def on_signal(headset, value):
        with state_lock:
            brain_state["signal_quality"] = value
        if value > 100:
            print(f"[BRAIN] ⚠️  Poor signal: {value} — adjust headset")

    headset.start()

    while running:
        time.sleep(0.05)

    headset.stop()
    print("[BRAIN] Headset disconnected.")


# ═══════════════════════════════════════════════════════════════════
#  ARM CONTROL LOOP THREAD
# ═══════════════════════════════════════════════════════════════════
def arm_control_thread(arm: ArmController):
    """
    Reads smoothed brainwave values and maps them to arm movements.
    Runs in its own thread to stay non-blocking.
    """
    global running
    last_blink = 0
    last_attention_state = "idle"

    print("[CONTROL] Arm control loop started. Think to control!")

    while running:
        with state_lock:
            attention  = brain_state["attention"]
            blink      = brain_state["blink"]
            signal_ok  = brain_state["signal_quality"] < 100

        if not signal_ok:
            time.sleep(0.1)
            continue

        # ── ATTENTION → GRIPPER + SHOULDER ──────────────────────
        if attention >= ATTENTION_LIFT_THRESHOLD:
            if last_attention_state != "lift":
                print(f"[CONTROL] 🧠 High focus ({attention}) → LIFT + GRIP")
                arm.grip(True)
                arm.lift(0.8)
                last_attention_state = "lift"

        elif attention >= ATTENTION_GRIP_THRESHOLD:
            if last_attention_state != "grip":
                print(f"[CONTROL] 🧠 Focus ({attention}) → GRIP")
                arm.grip(True)
                arm.lift(0.3)
                last_attention_state = "grip"

        else:
            if last_attention_state != "idle":
                print(f"[CONTROL] 😴 Relaxed ({attention}) → RELEASE")
                arm.grip(False)
                arm.lift(0.0)
                last_attention_state = "idle"

        # ── BLINK → BASE ROTATION ────────────────────────────────
        if blink > BLINK_ROTATE_THRESHOLD and blink != last_blink:
            print(f"[CONTROL] 👁️  Blink ({blink}) → ROTATE RIGHT")
            arm.rotate_base("right")
            last_blink = blink
            # Reset blink to prevent repeated triggers
            with state_lock:
                brain_state["blink"] = 0

        time.sleep(0.05)  # 20Hz control loop


# ═══════════════════════════════════════════════════════════════════
#  STATUS DISPLAY THREAD
# ═══════════════════════════════════════════════════════════════════
def status_display_thread():
    """Prints a live dashboard of brainwave values to terminal."""
    global running
    while running:
        with state_lock:
            att = brain_state["attention"]
            med = brain_state["meditation"]
            sig = brain_state["signal_quality"]

        bar_att = "█" * (att // 10) + "░" * (10 - att // 10)
        bar_med = "█" * (med // 10) + "░" * (10 - med // 10)
        signal_str = "GOOD ✓" if sig < 50 else f"POOR ({sig})"

        print(f"\r[DASHBOARD] Attention [{bar_att}] {att:3d}  "
              f"Meditation [{bar_med}] {med:3d}  "
              f"Signal: {signal_str}   ", end="", flush=True)
        time.sleep(0.5)


# ═══════════════════════════════════════════════════════════════════
#  DEMO MODE (run without headset for testing)
# ═══════════════════════════════════════════════════════════════════
def demo_mode(arm: ArmController):
    """Runs a demonstration sequence without the EEG headset."""
    print("\n[DEMO] Running arm demo sequence...")
    sequences = [
        ("Grip close", lambda: arm.grip(True)),
        ("Lift up",    lambda: arm.lift(0.9)),
        ("Rotate right", lambda: arm.rotate_base("right")),
        ("Rotate left",  lambda: arm.rotate_base("left")),
        ("Lower arm",  lambda: arm.lift(0.0)),
        ("Grip open",  lambda: arm.grip(False)),
        ("Home",       lambda: arm.reset_position()),
    ]
    for name, action in sequences:
        print(f"[DEMO] → {name}")
        action()
        time.sleep(1.5)
    print("[DEMO] Demo complete!")


# ═══════════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("  🧠 MIND-CONTROLLED ROBOT ARM  |  Course 1")
    print("=" * 60)

    arm = ArmController()

    demo = "--demo" in sys.argv
    if demo:
        demo_mode(arm)
    else:
        # Default Bluetooth serial port after rfcomm pairing
        bt_port = "/dev/rfcomm0"
        if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
            bt_port = sys.argv[1]

        threads = [
            threading.Thread(target=mindwave_thread,   args=(bt_port,), daemon=True),
            threading.Thread(target=arm_control_thread, args=(arm,),    daemon=True),
            threading.Thread(target=status_display_thread,              daemon=True),
        ]
        for t in threads:
            t.start()

        print("\n[MAIN] System running. Press CTRL+C to stop.\n")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n[MAIN] Shutting down...")
            running = False
            time.sleep(1)
            arm.cleanup()
            print("[MAIN] Goodbye! 🤖")
