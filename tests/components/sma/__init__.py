"""Tests for the sma integration."""
from unittest.mock import patch

MOCK_DEVICE = {
    "manufacturer": "SMA",
    "name": "SMA Device Name",
    "type": "Sunny Boy 3.6",
    "serial": "123456789",
}

MOCK_USER_INPUT = {
    "host": "1.1.1.1",
    "ssl": True,
    "verify_ssl": False,
    "group": "user",
    "password": "password",
}

MOCK_CUSTOM_SENSOR = {
    "name": "yesterday_consumption",
    "key": "6400_00543A01",
    "unit": "kWh",
    "factor": 1000,
}

MOCK_CUSTOM_SENSOR2 = {
    "name": "device_type_id",
    "key": "6800_08822000",
    "unit": "",
    "path": '"1"[0].val[0].tag',
}

MOCK_SETUP_DATA = dict(
    {
        "custom": {},
        "sensors": [],
    },
    **MOCK_USER_INPUT,
)

MOCK_CUSTOM_SETUP_DATA = dict(
    {
        "custom": {
            MOCK_CUSTOM_SENSOR["name"]: {
                "factor": MOCK_CUSTOM_SENSOR["factor"],
                "key": MOCK_CUSTOM_SENSOR["key"],
                "path": None,
                "unit": MOCK_CUSTOM_SENSOR["unit"],
            },
            MOCK_CUSTOM_SENSOR2["name"]: {
                "factor": 1.0,
                "key": MOCK_CUSTOM_SENSOR2["key"],
                "path": MOCK_CUSTOM_SENSOR2["path"],
                "unit": MOCK_CUSTOM_SENSOR2["unit"],
            },
        },
        "sensors": [],
    },
    **MOCK_USER_INPUT,
)


def _patch_async_setup_entry(return_value=True):
    return patch(
        "homeassistant.components.sma.async_setup_entry",
        return_value=return_value,
    )
