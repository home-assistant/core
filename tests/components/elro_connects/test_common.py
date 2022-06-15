"""Helpers for testing the Elro Connects integration."""

MOCK_DEVICE_STATUS_DATA = {
    1: {
        "device_type": "FIRE_ALARM",
        "signal": 3,
        "battery": 100,
        "device_state": "NORMAL",
        "device_status_data": {
            "cmdId": 19,
            "device_ID": 1,
            "device_name": "0013",
            "device_status": "0364AAFF",
        },
        "name": "Beganegrond",
    },
    2: {
        "device_type": "FIRE_ALARM",
        "signal": 4,
        "battery": 75,
        "device_state": "ALARM",
        "device_status_data": {
            "cmdId": 19,
            "device_ID": 2,
            "device_name": "0013",
            "device_status": "044B55FF",
        },
        "name": "Eerste etage",
    },
    4: {
        "device_type": "FIRE_ALARM",
        "signal": 1,
        "battery": 5,
        "device_state": "UNKNOWN",
        "device_status_data": {
            "cmdId": 19,
            "device_ID": 4,
            "device_name": "0013",
            "device_status": "0105FEFF",
        },
        "name": "Zolder",
    },
    5: {
        "device_type": "CO_ALARM",
        "signal": 255,
        "battery": 255,
        "device_state": "OFFLINE",
        "device_status_data": {
            "cmdId": 19,
            "device_ID": 5,
            "device_name": "2008",
            "device_status": "FFFFFFFF",
        },
        "name": "Corner",
    },
    6: {
        "name": "Device with unknown state",
    },
}
