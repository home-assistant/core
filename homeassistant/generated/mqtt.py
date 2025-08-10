"""Automatically generated file.

To update, run python3 -m script.hassfest
"""

MQTT = {
    "drop_connect": [
        "drop_connect/discovery/#",
    ],
    "dsmr_reader": [
        "dsmr/#",
    ],
    "esphome": [
        "esphome/discover/#",
    ],
    "fully_kiosk": [
        "fully/deviceInfo/+",
    ],
    "pglab": [
        "pglab/discovery/#",
    ],
    "qbus": [
        "cloudapp/QBUSMQTTGW/state",
        "cloudapp/QBUSMQTTGW/config",
        "cloudapp/QBUSMQTTGW/+/state",
    ],
    "tasmota": [
        "tasmota/discovery/#",
    ],
}
