"""Define fixtures for the The Things Network tests."""

from unittest.mock import AsyncMock, patch

import pytest
from ttn_client import TTNBinarySensorValue, TTNDeviceTrackerValue, TTNSensorValue

from homeassistant.components.thethingsnetwork.const import (
    CONF_APP_ID,
    DOMAIN,
    TTN_API_HOST,
)
from homeassistant.const import CONF_API_KEY, CONF_HOST

from tests.common import MockConfigEntry

HOST = "example.com"
APP_ID = "my_app"
API_KEY = "my_api_key"

DEVICE_ID = "my_device"
DEVICE_ID_2 = "my_device_2"
SENSOR_FIELD = "a_sensor"
SENSOR_FIELD_2 = "a_sensor"
SENSOR_FIELD_VALUE = 42
BINARY_SENSOR_FIELD = "a_binary_sensor"
BINARY_SENSOR_FIELD_2 = "a_binary_sensor"
BINARY_SENSOR_FIELD_VALUE = True
TRACKER_FIELD = "gps"
TRACKER_FIELD_2 = "gps"
TRACKER_FIELD_VALUE = {
    "longitude": 1.23,
    "latitude": 4.56,
    "altitude": 7.89,
}

DATA = {
    DEVICE_ID: {
        SENSOR_FIELD: TTNSensorValue(
            {
                "end_device_ids": {"device_id": DEVICE_ID},
                "received_at": "2024-03-11T08:49:11.153738893Z",
            },
            SENSOR_FIELD,
            SENSOR_FIELD_VALUE,
        ),
        BINARY_SENSOR_FIELD: TTNBinarySensorValue(
            {
                "end_device_ids": {"device_id": DEVICE_ID},
                "received_at": "2024-03-11T08:49:11.153738893Z",
            },
            BINARY_SENSOR_FIELD,
            BINARY_SENSOR_FIELD_VALUE,
        ),
        TRACKER_FIELD: TTNDeviceTrackerValue(
            {
                "end_device_ids": {"device_id": DEVICE_ID},
                "received_at": "2024-03-11T08:49:11.153738893Z",
            },
            TRACKER_FIELD,
            TRACKER_FIELD_VALUE,
        ),
    }
}

DATA_UPDATE = {
    DEVICE_ID: {
        SENSOR_FIELD: TTNSensorValue(
            {
                "end_device_ids": {"device_id": DEVICE_ID},
                "received_at": "2024-03-12T08:49:11.153738893Z",
            },
            SENSOR_FIELD,
            SENSOR_FIELD_VALUE,
        ),
        BINARY_SENSOR_FIELD: TTNBinarySensorValue(
            {
                "end_device_ids": {"device_id": DEVICE_ID},
                "received_at": "2024-03-11T08:49:11.153738893Z",
            },
            BINARY_SENSOR_FIELD,
            BINARY_SENSOR_FIELD_VALUE,
        ),
        TRACKER_FIELD: TTNDeviceTrackerValue(
            {
                "end_device_ids": {"device_id": DEVICE_ID},
                "received_at": "2024-03-11T08:49:11.153738893Z",
            },
            TRACKER_FIELD,
            TRACKER_FIELD_VALUE,
        ),
    },
    DEVICE_ID_2: {
        SENSOR_FIELD_2: TTNSensorValue(
            {
                "end_device_ids": {"device_id": DEVICE_ID_2},
                "received_at": "2024-03-12T08:49:11.153738893Z",
            },
            SENSOR_FIELD_2,
            SENSOR_FIELD_VALUE,
        ),
        BINARY_SENSOR_FIELD_2: TTNBinarySensorValue(
            {
                "end_device_ids": {"device_id": DEVICE_ID_2},
                "received_at": "2024-03-11T08:49:11.153738893Z",
            },
            BINARY_SENSOR_FIELD_2,
            BINARY_SENSOR_FIELD_VALUE,
        ),
        TRACKER_FIELD_2: TTNDeviceTrackerValue(
            {
                "end_device_ids": {"device_id": DEVICE_ID_2},
                "received_at": "2024-03-11T08:49:11.153738893Z",
            },
            TRACKER_FIELD_2,
            TRACKER_FIELD_VALUE,
        ),
    },
}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=APP_ID,
        title=APP_ID,
        data={
            CONF_APP_ID: APP_ID,
            CONF_HOST: TTN_API_HOST,
            CONF_API_KEY: API_KEY,
        },
    )


@pytest.fixture
def mock_ttnclient():
    """Mock TTNClient."""

    with (
        patch(
            "homeassistant.components.thethingsnetwork.coordinator.TTNClient",
            autospec=True,
        ) as ttn_client,
        patch(
            "homeassistant.components.thethingsnetwork.config_flow.TTNClient",
            new=ttn_client,
        ),
    ):
        instance = ttn_client.return_value
        instance.fetch_data = AsyncMock(return_value=DATA)
        yield ttn_client
