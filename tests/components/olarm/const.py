"""Constants used across Olarm tests."""

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"

# API systems response (OlarmFlowClient uses "devices" terminology)
MOCK_SYSTEMS_RESPONSE = {
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

# API system response (OlarmFlowClient uses "device" terminology)
MOCK_SYSTEM_RESPONSE = {
    "deviceName": "Test System",
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
