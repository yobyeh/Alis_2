#!/usr/bin/env bash
set -euo pipefail

# Alis Project Setup & Runner (system Python, no venv, uses LOCAL driver files)
# - Installs system Python packages (Pi 5–friendly GPIO backend)
# - (Optionally) enables SPI
# - Ensures app/ and driver/ are importable packages (adds __init__.py if missing)
# - Verifies imports (Pillow, numpy, spidev, gpiozero, lgpio + local driver)
# - Runs app/main.py with gpiozero using the lgpio pin factory when --run is passed
#
# Usage:
#   chmod +x Alis_Script.sh
#   sudo ./Alis_Script.sh                 # install & verify
#   sudo ./Alis_Script.sh --enable-spi    # also enable SPI
#   sudo ./Alis_Script.sh --run           # then run Alis

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"
export PROJECT_ROOT
APP_DIR="$PROJECT_ROOT/app"
DRIVER_DIR="$PROJECT_ROOT/driver"
APP_MAIN="$APP_DIR/main.py"

ENABLE_SPI=0
RUN_APP=0
[[ $# -eq 0 ]] && echo "No options provided"
for arg in "$@"; do
  case "$arg" in
    --enable-spi) ENABLE_SPI=1 ;;
    --run) RUN_APP=1 ;;
    *) echo "Unknown arg: $arg" ;;
  esac
done

require_root() {
  if [[ $EUID -ne 0 ]]; then
    echo "Please run with sudo: sudo $0 [--enable-spi] [--run]"
    exit 1
  fi
}
step() { echo -e "\n[$(date +%H:%M:%S)] $*"; }

require_root
TARGET_USER="${SUDO_USER:-$USER}"

# 1) System packages (use distro packages for stability)
step "Installing system Python packages…"
apt update
apt install -y \
  python3 python3-pip \
  python3-pil python3-numpy python3-spidev python3-gpiozero python3-lgpio \
  raspi-config

# 2) Optionally enable SPI (Bookworm uses /boot/firmware/config.txt)
if [[ $ENABLE_SPI -eq 1 ]]; then
  step "Enabling SPI (non-interactive)…"
  raspi-config nonint do_spi 0 || true
  CFG="/boot/firmware/config.txt"
  if ! grep -qE '^\s*dtparam=spi=on' "$CFG" 2>/dev/null; then
    echo "dtparam=spi=on" >> "$CFG"
    echo "Added dtparam=spi=on to $CFG"
  fi
  # allow non-root access to SPI/GPIO device files
  usermod -aG spi,gpio "$TARGET_USER" || true
  SPI_CHANGED=1
else
  SPI_CHANGED=0
fi

# 3) Ensure project structure is correct and local driver is used
step "Checking project structure…"
if [[ ! -d "$APP_DIR" || ! -f "$APP_MAIN" ]]; then
  echo "ERROR: $APP_MAIN not found. Create app/main.py first."
  exit 1
fi
if [[ ! -d "$DRIVER_DIR" ]]; then
  echo "ERROR: $DRIVER_DIR not found. Place LCD_2inch.py and lcdconfig.py into ./driver/"
  exit 1
fi
# Make them Python packages so imports work with -m app.main
[[ -f "$APP_DIR/__init__.py" ]] || { echo "# Alis app package" > "$APP_DIR/__init__.py"; chown "$TARGET_USER":"$TARGET_USER" "$APP_DIR/__init__.py"; }
[[ -f "$DRIVER_DIR/__init__.py" ]] || { echo "# Alis driver package" > "$DRIVER_DIR/__init__.py"; chown "$TARGET_USER":"$TARGET_USER" "$DRIVER_DIR/__init__.py"; }

# 4) Verify core imports using system Python (uses LOCAL driver, no downloads)
step "Verifying Python modules and local driver (system Python)…"
python3 - <<'PY'
import sys, importlib, pathlib, os
def ok(x): print(x, "OK")
def fail(tag, e): 
    print(tag, "FAILED:", e); sys.exit(1)

mods = ["PIL", "numpy", "spidev", "gpiozero"]
for m in mods:
    try: importlib.import_module(m); ok(m)
    except Exception as e: fail(m, e)

# lgpio is the Pi 5–friendly backend for gpiozero
try:
    import lgpio; ok("lgpio")
except Exception as e:
    fail("lgpio", e)

# Ensure local driver import works from PROJECT_ROOT
root = pathlib.Path(os.environ["PROJECT_ROOT"])
if str(root) not in sys.path:
    sys.path.insert(0, str(root))
try:
    from driver import LCD_2inch; ok("driver import")
except Exception as e:
    fail("driver import", e)
PY

# 5) Run the app if requested (forces lgpio backend to avoid RPi.GPIO on Pi 5)
if [[ $RUN_APP -eq 1 ]]; then
  step "Launching Alis (app/main.py) with lgpio backend… (Ctrl+C to quit)"
  sudo -u "$TARGET_USER" bash -lc "cd '$PROJECT_ROOT' && \
    export GPIOZERO_PIN_FACTORY=lgpio && \
    python3 -m app.main"
fi

if [[ "${SPI_CHANGED:-0}" -eq 1 ]]; then
  echo -e "\nNOTE: SPI was just enabled. If /dev/spidev* is missing, reboot with: sudo reboot"
fi

echo -e "\nAll set."
