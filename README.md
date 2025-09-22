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

## Usage
Run the main application to launch the menu system on the LCD:

```bash
python3 app/main.py
```

Use the connected buttons to navigate the on‑screen menu.  Settings are stored in `settings.json` and persist across restarts.

## Quick Start Example


This boots the UI with the default menu defined in `menu.json`.

