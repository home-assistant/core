"""Constants for the Home Assistant Yellow integration."""

DOMAIN = "homeassistant_yellow"

MODEL = "Home Assistant Yellow"
MANUFACTURER = "Nabu Casa"

RADIO_DEVICE = "/dev/ttyAMA1"

ZHA_HW_DISCOVERY_DATA = {
    "name": "Yellow",
    "port": {
        "path": RADIO_DEVICE,
        "baudrate": 115200,
        "flow_control": "hardware",
    },
    "radio_type": "efr32",
}

FIRMWARE = "firmware"
FIRMWARE_VERSION = "firmware_version"
ZHA_DOMAIN = "zha"

NABU_CASA_FIRMWARE_RELEASES_URL = (
    "https://api.github.com/repos/NabuCasa/silabs-firmware-builder/releases/latest"
)
