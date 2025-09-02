# Alis_2

## Project Description
Alis 2 is a Python-driven menu interface for Raspberry Pi devices equipped with a small Waveshare LCD.  The application renders a themed UI and listens for button input through dedicated threads, persisting configuration to disk so that settings survive reboots.

## Hardware Dependencies
- Raspberry Pi with SPI enabled
- Waveshare 2" SPI LCD (tested with the Waveshare 2 inch module)
- Momentary buttons wired to GPIO pins
- Python library [`gpiozero`](https://gpiozero.readthedocs.io/) using the [`lgpio`](https://pypi.org/project/lgpio/) backend for handling button input (no `RPi.GPIO` required)

## Setup
1. Enable SPI on the Raspberry Pi (`sudo raspi-config`).
2. Clone this repository and move into the project directory.
3. Run the setup script, which installs all required Python packages and can optionally enable SPI or launch the app:

    ```bash
    chmod +x Alis_Script.sh
    sudo ./Alis_Script.sh [--enable-spi] [--run] [--skip-pip-upgrade]
    ```

    Use `--enable-spi` to enable SPI, `--run` to launch the application after installation, and `--skip-pip-upgrade` to bypass the pip upgrade step. The script attempts to upgrade `pip` but will continue even if the upgrade fails. It installs packages that configure `gpiozero` to use the `lgpio` backend, so `RPi.GPIO` is not required.


## Usage
Run the main application to launch the menu system on the LCD:

```bash
python3 app/main.py
```

Use the connected buttons to navigate the on‑screen menu.  Settings are stored in `settings.json` and persist across restarts.

### Bluetooth file upload

An optional Bluetooth server is available to receive files from the companion iOS app.  Run the receiver on the Pi:

```
python3 app/file_receiver.py
```

Files sent from the app are stored under `uploads/` within the project directory.

## Quick Start Example

```bash
git clone <repository-url>
cd Alis_2
chmod +x Alis_Script.sh
sudo ./Alis_Script.sh --run
```

This boots the UI with the default menu defined in `menu.json`.

## Contribution Guidelines
Contributions are welcome!  Please open an issue or pull request with proposed changes.  Keep commits focused, follow Python best practices, and run the available tests before submitting.
