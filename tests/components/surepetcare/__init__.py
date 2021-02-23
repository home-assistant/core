"""Tests for Sure Petcare integration."""
from unittest.mock import patch

from homeassistant.components.surepetcare.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

HOUSEHOLD_ID = "household-id"
HUB_ID = "hub-id"

MOCK_HUB = {
    "id": HUB_ID,
    "product_id": 1,
    "household_id": HOUSEHOLD_ID,
    "name": "Hub",
    "status": {"online": True, "led_mode": 0, "pairing_mode": 0},
}

MOCK_FEEDER = {
    "id": 12345,
    "product_id": 4,
    "household_id": HOUSEHOLD_ID,
    "name": "Feeder",
    "parent": {"product_id": 1, "id": HUB_ID},
    "status": {
        "battery": 6.4,
        "locking": {"mode": 0},
        "learn_mode": 0,
        "signal": {"device_rssi": 60, "hub_rssi": 65},
    },
}

MOCK_CAT_FLAP = {
    "id": 13579,
    "product_id": 6,
    "household_id": HOUSEHOLD_ID,
    "name": "Cat Flap",
    "parent": {"product_id": 1, "id": HUB_ID},
    "status": {
        "battery": 6.4,
        "locking": {"mode": 0},
        "learn_mode": 0,
        "signal": {"device_rssi": 65, "hub_rssi": 64},
    },
}

MOCK_PET_FLAP = {
    "id": 13576,
    "product_id": 3,
    "household_id": HOUSEHOLD_ID,
    "name": "Pet Flap",
    "parent": {"product_id": 1, "id": HUB_ID},
    "status": {
        "battery": 6.4,
        "locking": {"mode": 0},
        "learn_mode": 0,
        "signal": {"device_rssi": 70, "hub_rssi": 65},
    },
}

MOCK_PET = {
    "id": 24680,
    "household_id": HOUSEHOLD_ID,
    "name": "Pet",
    "position": {"since": "2020-08-23T23:10:50", "where": 1},
    "status": {},
}

MOCK_API_DATA = {
    "devices": [MOCK_HUB, MOCK_CAT_FLAP, MOCK_PET_FLAP, MOCK_FEEDER],
    "pets": [MOCK_PET],
}

MOCK_CONFIG = {
    DOMAIN: {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        "feeders": [12345],
        "flaps": [13579, 13576],
        "pets": [24680],
    },
}


def _patch_sensor_setup():
    return patch(
        "homeassistant.components.surepetcare.sensor.async_setup_platform",
        return_value=True,
    )
