"""Const for the aidot tests."""

from aidot.const import CONF_DEVICE_LIST

TEST_COUNTRY = "United States"
TEST_EMAIL = "test@gmail.com"
TEST_PASSWORD = "123456"
TEST_REGION = "us"

TEST_LOGIN_RESP = {
    "id": "314159263367458941151",
    "accessToken": "1234567891011121314151617181920",
    "refreshToken": "2021222324252627282930313233343",
    "expiresIn": 10000,
    "nickname": TEST_EMAIL,
    "username": TEST_EMAIL,
}

ENTITY_LIGHT = "light.test_light"
ENTITY_LIGHT2 = "light.test_light2"
LIGHT_DOMAIN = "light"

TEST_DEVICE1 = {
    "id": "device_id",
    "name": "Test Light",
    "modelId": "aidot.light.rgbw",
    "mac": "AA:BB:CC:DD:EE:FF",
    "hardwareVersion": "1.0",
    "type": "light",
    "aesKey": ["mock_aes_key"],
    "product": {
        "id": "test_product",
        "serviceModules": [
            {"identity": "control.light.rgbw"},
            {
                "identity": "control.light.cct",
                "properties": [{"identity": "CCT", "maxValue": 6500, "minValue": 2700}],
            },
        ],
    },
}

TEST_DEVICE2 = {
    "id": "device_id2",
    "name": "Test Light2",
    "modelId": "aidot.light.rgbw",
    "mac": "AA:BB:CC:DD:EE:EE",
    "hardwareVersion": "1.0",
    "type": "light",
    "aesKey": ["mock_aes_key"],
    "product": {
        "id": "test_product",
        "serviceModules": [
            {"identity": "control.light.rgbw"},
            {
                "identity": "control.light.cct",
                "properties": [{"identity": "CCT", "maxValue": 6500, "minValue": 2700}],
            },
        ],
    },
}

TEST_DEVICE_LIST = {CONF_DEVICE_LIST: [TEST_DEVICE1]}
TEST_MULTI_DEVICE_LIST = {CONF_DEVICE_LIST: [TEST_DEVICE1, TEST_DEVICE2]}
