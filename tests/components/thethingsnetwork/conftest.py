"""Define fixtures for the The Things Network tests."""

from unittest.mock import AsyncMock, patch

import pytest
from ttn_client import TTNSensorAttribute, TTNSensorValue

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
DEVICE_FIELD = "a_field"
DEVICE_FIELD_2 = "a_field_2"
DEVICE_FIELD_VALUE = 42

_BASE_MESSAGE = {
    "end_device_ids": {"device_id": DEVICE_ID},
    "received_at": "2024-03-11T08:49:11.153738893Z",
}

_UPDATED_MESSAGE = {
    "end_device_ids": {"device_id": DEVICE_ID},
    "received_at": "2024-03-12T08:49:11.153738893Z",
}

_UPDATED_MESSAGE_2 = {
    "end_device_ids": {"device_id": DEVICE_ID_2},
    "received_at": "2024-03-12T08:49:11.153738893Z",
}

DATA = {
    DEVICE_ID: {
        DEVICE_FIELD: TTNSensorValue(
            _BASE_MESSAGE,
            DEVICE_FIELD,
            DEVICE_FIELD_VALUE,
        )
    }
}

DATA_UPDATE = {
    DEVICE_ID: {
        DEVICE_FIELD: TTNSensorValue(
            _UPDATED_MESSAGE,
            DEVICE_FIELD,
            DEVICE_FIELD_VALUE,
        )
    },
    DEVICE_ID_2: {
        DEVICE_FIELD_2: TTNSensorValue(
            _UPDATED_MESSAGE_2,
            DEVICE_FIELD_2,
            DEVICE_FIELD_VALUE,
        )
    },
}

DATA_WITH_ATTRS = {
    DEVICE_ID: {
        "BatV": TTNSensorValue(
            _BASE_MESSAGE,
            "BatV",
            3.6,
        ),
        "temperature": TTNSensorValue(
            _BASE_MESSAGE,
            "temperature",
            22.5,
        ),
        "_sensor_attr_BatV_unit": TTNSensorAttribute(
            _BASE_MESSAGE,
            "_sensor_attr_BatV_unit",
            "V",
        ),
        "_sensor_attr_BatV_device_class": TTNSensorAttribute(
            _BASE_MESSAGE,
            "_sensor_attr_BatV_device_class",
            "voltage",
        ),
        "_sensor_attr_BatV_state_class": TTNSensorAttribute(
            _BASE_MESSAGE,
            "_sensor_attr_BatV_state_class",
            "measurement",
        ),
        "_sensor_attr_temperature_unit": TTNSensorAttribute(
            _BASE_MESSAGE,
            "_sensor_attr_temperature_unit",
            "°C",
        ),
        "_sensor_attr_temperature_device_class": TTNSensorAttribute(
            _BASE_MESSAGE,
            "_sensor_attr_temperature_device_class",
            "temperature",
        ),
        "_sensor_attr_temperature_state_class": TTNSensorAttribute(
            _BASE_MESSAGE,
            "_sensor_attr_temperature_state_class",
            "measurement",
        ),
        "_sensor_attr_temperature_friendly_name": TTNSensorAttribute(
            _BASE_MESSAGE,
            "_sensor_attr_temperature_friendly_name",
            "Room Temperature",
        ),
        "_sensor_attr_temperature_suggested_display_precision": TTNSensorAttribute(
            _BASE_MESSAGE,
            "_sensor_attr_temperature_suggested_display_precision",
            "1",
        ),
    }
}

DATA_WITH_ENTITY_CATEGORY = {
    DEVICE_ID: {
        "rssi": TTNSensorValue(
            _BASE_MESSAGE,
            "rssi",
            -80,
        ),
        "_sensor_attr_rssi_entity_category": TTNSensorAttribute(
            _BASE_MESSAGE,
            "_sensor_attr_rssi_entity_category",
            "diagnostic",
        ),
    }
}

DATA_WITH_INVALID_ATTRS = {
    DEVICE_ID: {
        "sensor_x": TTNSensorValue(
            _BASE_MESSAGE,
            "sensor_x",
            99,
        ),
        "_sensor_attr_sensor_x_device_class": TTNSensorAttribute(
            _BASE_MESSAGE,
            "_sensor_attr_sensor_x_device_class",
            "not_a_real_class",
        ),
    }
}

DATA_WITH_UNDERSCORE_FIELD = {
    DEVICE_ID: {
        "_internal_field": TTNSensorValue(
            _BASE_MESSAGE,
            "_internal_field",
            99,
        ),
        DEVICE_FIELD: TTNSensorValue(
            _BASE_MESSAGE,
            DEVICE_FIELD,
            DEVICE_FIELD_VALUE,
        ),
    }
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
