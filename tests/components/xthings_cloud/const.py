"""Constants for Xthings Cloud integration tests."""

MOCK_EMAIL = "test@example.com"
MOCK_PASSWORD = "test_password"
MOCK_TOKEN = "mock_token"
MOCK_REFRESH_TOKEN = "mock_refresh_token"
MOCK_USER_ID = "02c7badf2b3d44d953b48b579eb9eeb5"

MOCK_DEVICE_LIGHT_FULL = {
    "id": "dev_light_001",
    "name": "Bedroom Light",
    "type": "light",
    "model": "XT-LT200",
    "version": "2.0.1",
    "online": True,
    "status": {
        "on": True,
        "brightness": 75,
        "color_type": 0,
        "hue": 150,
        "saturation": 80,
        "lightness": 54,
        "temperature": 4000,
    },
}

MOCK_DEVICE_LIGHT_BRIGHTNESS_ONLY = {
    "id": "dev_light_002",
    "name": "Hallway Light",
    "type": "light",
    "model": "XT-LT100",
    "version": "1.0.0",
    "online": True,
    "status": {
        "on": False,
        "brightness": 50,
    },
}

MOCK_DEVICE_LIGHT_ONOFF = {
    "id": "dev_light_003",
    "name": "Porch Light",
    "type": "light",
    "model": "XT-LT050",
    "version": "1.0.0",
    "online": True,
    "status": {
        "on": True,
    },
}
