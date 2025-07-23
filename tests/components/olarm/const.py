"""Constants used across Olarm tests."""

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"

# API devices response
MOCK_DEVICES_RESPONSE = {
    "userId": "abcd4ffb-8131-4de0-9416-a89abde63def",
    "page": 1,
    "pageLength": 100,
    "pageCount": 1,
    "search": "",
    "data": [
        {
            "deviceId": "123cf304-1dcf-48c6-b79b-4ce4640e3def",
            "deviceName": "Demo Olarm #0G",
            "deviceSerial": "P2BAEDN1",
            "deviceType": "OLARMPRO",
            "deviceAlarmType": "paradox",
            "deviceAlarmTypeDetail": "",
            "deviceTimestamp": 1750854025916,
            "deviceStatus": "online",
        }
    ],
}

# API device response
MOCK_DEVICE_RESPONSE = {
    "deviceName": "Test Device",
    "deviceState": {
        "zones": ["a", "c", "b"],
        "powerAC": "ok",
    },
    "deviceLinks": {},
    "deviceIO": {},
    "deviceProfile": {
        "zonesLabels": ["Front Door", "Window", "Motion"],
        "zonesTypes": [10, 11, 20],
    },
    "deviceProfileLinks": {},
    "deviceProfileIO": {},
}
