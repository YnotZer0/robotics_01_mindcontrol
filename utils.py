"""
╔══════════════════════════════════════════════════════════════════╗
║   SHARED UTILITIES — used across all 6 courses                  ║
║   utils.py                                                       ║
╚══════════════════════════════════════════════════════════════════╝
"""

import time
import threading
import collections
import json
from pathlib import Path
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════
#  SMOOTH VALUE — rolling average for noisy sensor data
# ═══════════════════════════════════════════════════════════════════
class SmoothValue:
    """
    Keeps a rolling average of the last N readings.
    Essential for filtering noisy sensor data (EEG, audio, etc.)

    Usage:
        smooth = SmoothValue(window=5)
        smooth.add(42)
        smooth.add(39)
        print(smooth.get())   # → 40.5
    """

    def __init__(self, window: int = 5, default: float = 0.0):
        self._buffer  = collections.deque([default] * window, maxlen=window)
        self._default = default

    def add(self, value: float):
        self._buffer.append(value)

    def get(self) -> float:
        return sum(self._buffer) / len(self._buffer)

    def reset(self):
        self._buffer = collections.deque(
            [self._default] * self._buffer.maxlen,
            maxlen=self._buffer.maxlen
        )


# ═══════════════════════════════════════════════════════════════════
#  RATE LIMITER — prevent functions from firing too frequently
# ═══════════════════════════════════════════════════════════════════
class RateLimiter:
    """
    Allows an action to happen at most once per `interval` seconds.

    Usage:
        limiter = RateLimiter(interval=5.0)
        if limiter.ready():
            do_something()   # Only runs every 5 seconds
    """

    def __init__(self, interval: float):
        self.interval  = interval
        self._last_run = 0.0

    def ready(self) -> bool:
        if time.time() - self._last_run >= self.interval:
            self._last_run = time.time()
            return True
        return False

    def reset(self):
        self._last_run = 0.0


# ═══════════════════════════════════════════════════════════════════
#  THREAD WORKER — run a function in a background daemon thread
# ═══════════════════════════════════════════════════════════════════
class BackgroundWorker:
    """
    Runs a function repeatedly in a background thread.

    Usage:
        def my_task():
            print("running...")

        worker = BackgroundWorker(my_task, interval=1.0)
        worker.start()
        # ... do other things ...
        worker.stop()
    """

    def __init__(self, func, interval: float = 0.1, name: str = "worker"):
        self._func     = func
        self._interval = interval
        self._name     = name
        self._running  = False
        self._thread   = None

    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True, name=self._name)
        self._thread.start()
        print(f"[WORKER] '{self._name}' started (every {self._interval}s)")

    def _loop(self):
        while self._running:
            try:
                self._func()
            except Exception as e:
                print(f"[WORKER] '{self._name}' error: {e}")
            time.sleep(self._interval)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        print(f"[WORKER] '{self._name}' stopped")


# ═══════════════════════════════════════════════════════════════════
#  DATA LOGGER — simple JSON line logger for sensor data
# ═══════════════════════════════════════════════════════════════════
class DataLogger:
    """
    Logs sensor readings to a JSON-lines file for later analysis.
    Each line is a valid JSON object with a timestamp.

    Usage:
        logger = DataLogger("readings.jsonl")
        logger.log({"temperature": 22.5, "humidity": 60})
    """

    def __init__(self, filepath: str, max_lines: int = 10000):
        self.filepath  = Path(filepath)
        self.max_lines = max_lines
        self._lock     = threading.Lock()
        print(f"[LOGGER] Logging to {filepath}")

    def log(self, data: dict):
        entry = {"ts": datetime.now().isoformat(), **data}
        with self._lock:
            with open(self.filepath, "a") as f:
                f.write(json.dumps(entry) + "\n")

    def read_recent(self, n: int = 100) -> list[dict]:
        if not self.filepath.exists():
            return []
        with open(self.filepath) as f:
            lines = f.readlines()
        return [json.loads(line) for line in lines[-n:] if line.strip()]


# ═══════════════════════════════════════════════════════════════════
#  SERVO HELPER — map a value range to a servo angle range
# ═══════════════════════════════════════════════════════════════════
def map_value(value: float,
              in_min: float, in_max: float,
              out_min: float, out_max: float) -> float:
    """
    Linearly maps a value from one range to another.
    Like Arduino's map() function.

    Example:
        map_value(50, 0, 100, 0, 180)  → 90.0   (50% → 90 degrees)
        map_value(0.5, 0, 1, 30, 150)  → 90.0
    """
    if in_max == in_min:
        return out_min
    ratio  = (value - in_min) / (in_max - in_min)
    result = out_min + ratio * (out_max - out_min)
    return max(min(out_min, out_max), min(max(out_min, out_max), result))


def clamp(value: float, minimum: float, maximum: float) -> float:
    """Clamp a value between a minimum and maximum."""
    return max(minimum, min(maximum, value))


# ═══════════════════════════════════════════════════════════════════
#  TERMINAL COLOURS — for pretty console output
# ═══════════════════════════════════════════════════════════════════
class Colour:
    RED    = "\033[91m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    BLUE   = "\033[94m"
    PURPLE = "\033[95m"
    CYAN   = "\033[96m"
    RESET  = "\033[0m"
    BOLD   = "\033[1m"

    @staticmethod
    def info(msg):    print(f"{Colour.CYAN}[INFO]{Colour.RESET} {msg}")
    @staticmethod
    def success(msg): print(f"{Colour.GREEN}[OK]{Colour.RESET} {msg}")
    @staticmethod
    def warn(msg):    print(f"{Colour.YELLOW}[WARN]{Colour.RESET} {msg}")
    @staticmethod
    def error(msg):   print(f"{Colour.RED}[ERROR]{Colour.RESET} {msg}")


# ═══════════════════════════════════════════════════════════════════
#  HARDWARE CHECK — verify GPIO and I2C are available
# ═══════════════════════════════════════════════════════════════════
def check_hardware() -> dict:
    """
    Checks availability of common hardware components.
    Returns a dict of component → available (bool).
    """
    results = {}

    # GPIO
    try:
        import RPi.GPIO as GPIO
        results["gpio"] = True
    except ImportError:
        results["gpio"] = False
        Colour.warn("RPi.GPIO not available — GPIO features disabled")

    # I2C (for PCA9685, OLED, etc.)
    try:
        import board, busio
        i2c = busio.I2C(board.SCL, board.SDA)
        i2c.deinit()
        results["i2c"] = True
    except Exception:
        results["i2c"] = False
        Colour.warn("I2C not available — check SDA/SCL connections")

    # Camera
    try:
        import cv2
        cam = cv2.VideoCapture(0)
        ok, _ = cam.read()
        cam.release()
        results["camera"] = ok
    except Exception:
        results["camera"] = False

    # Audio
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        results["audio"] = len(devices) > 0
    except Exception:
        results["audio"] = False

    print("\n─── HARDWARE CHECK ───")
    for component, available in results.items():
        status = f"{Colour.GREEN}✓ Available{Colour.RESET}" if available else f"{Colour.RED}✗ Not found{Colour.RESET}"
        print(f"  {component:<12} {status}")
    print()

    return results


# ═══════════════════════════════════════════════════════════════════
#  QUICK TEST — run this file directly to test utilities
# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 50)
    print("  SHARED UTILITIES — Self Test")
    print("=" * 50)

    # Test SmoothValue
    sv = SmoothValue(window=4)
    for v in [10, 20, 30, 40]:
        sv.add(v)
    assert sv.get() == 25.0, f"Expected 25.0, got {sv.get()}"
    Colour.success("SmoothValue works correctly")

    # Test RateLimiter
    rl = RateLimiter(interval=0.1)
    assert rl.ready() == True
    assert rl.ready() == False
    time.sleep(0.15)
    assert rl.ready() == True
    Colour.success("RateLimiter works correctly")

    # Test map_value
    assert map_value(50, 0, 100, 0, 180) == 90.0
    assert map_value(0, 0, 100, 0, 180)  == 0.0
    Colour.success("map_value works correctly")

    # Test DataLogger
    logger = DataLogger("/tmp/test_log.jsonl")
    logger.log({"test": True, "value": 42})
    entries = logger.read_recent(1)
    assert entries[0]["value"] == 42
    Colour.success("DataLogger works correctly")

    # Hardware check
    check_hardware()

    print("All utility tests passed! ✓")
