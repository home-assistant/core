"""Constants for the Home Assistant Yellow integration."""

DOMAIN = "homeassistant_yellow"

ISSUE_CM4_UNSEATED = "cm4_unseated"
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
