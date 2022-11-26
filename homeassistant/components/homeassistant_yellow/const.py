"""Constants for the Home Assistant Yellow integration."""

DOMAIN = "homeassistant_yellow"

ZHA_HW_DISCOVERY_DATA = {
    "name": "Yellow",
    "port": {
        "path": "/dev/ttyAMA1",
        "baudrate": 115200,
        "flow_control": "hardware",
    },
    "radio_type": "efr32",
}
