"""Define fixtures for the The Things Network tests."""

from unittest.mock import AsyncMock, patch

import pytest
from ttn_client import TTNSensorValue

from homeassistant.components.thethingsnetwork.const import (
    CONF_API_KEY,
    CONF_APP_ID,
    CONF_HOSTNAME,
    DOMAIN,
    OPTIONS_FIELD_ENTITY_TYPE,
    OPTIONS_FIELD_ENTITY_TYPE_SENSOR,
    OPTIONS_MENU_EDIT_FIELDS,
    TTN_API_HOSTNAME,
)

from tests.common import MockConfigEntry

HOSTNAME = "example.com"
APP_ID = "my_app"
API_KEY = "my_api_key"

DEVICE_ID = "my_device"
DEVICE_ID_2 = "my_device_2"
DEVICE_FIELD = "a_field"
DEVICE_FIELD_2 = "a_field_2"
DEVICE_FIELD_VALUE = 42

DATA = {
    DEVICE_ID: {
        DEVICE_FIELD: TTNSensorValue(
            {
                "end_device_ids": {"device_id": DEVICE_ID},
                "received_at": "2024-03-11T08:49:11.153738893Z",
            },
            DEVICE_FIELD,
            DEVICE_FIELD_VALUE,
        )
    }
}

DATA_UPDATE = {
    DEVICE_ID: {
        DEVICE_FIELD: TTNSensorValue(
            {
                "end_device_ids": {"device_id": DEVICE_ID},
                "received_at": "2024-03-12T08:49:11.153738893Z",
            },
            DEVICE_FIELD,
            DEVICE_FIELD_VALUE,
        )
    },
    DEVICE_ID_2: {
        DEVICE_FIELD_2: TTNSensorValue(
            {
                "end_device_ids": {"device_id": DEVICE_ID_2},
                "received_at": "2024-03-12T08:49:11.153738893Z",
            },
            DEVICE_FIELD_2,
            DEVICE_FIELD_VALUE,
        )
    },
}

CONFIG_ENTRY = MockConfigEntry(
    domain=DOMAIN,
    unique_id=APP_ID,
    title=APP_ID,
    data={
        CONF_APP_ID: APP_ID,
        CONF_HOSTNAME: TTN_API_HOSTNAME,
        CONF_API_KEY: API_KEY,
    },
    options={
        OPTIONS_MENU_EDIT_FIELDS: {
            DEVICE_FIELD: {OPTIONS_FIELD_ENTITY_TYPE: OPTIONS_FIELD_ENTITY_TYPE_SENSOR}
        }
    },
)


@pytest.fixture
def mock_TTNClient_coordinator():
    """Mock TTNClient."""

    with patch(
        "homeassistant.components.thethingsnetwork.coordinator.TTNClient", autospec=True
    ) as TTNClient:
        instance = TTNClient.return_value
        instance.fetch_data = AsyncMock(return_value=DATA)
        yield TTNClient


@pytest.fixture
def mock_TTNClient_config_flow():
    """Mock TTNClient."""

    with patch(
        "homeassistant.components.thethingsnetwork.config_flow.TTNClient", autospec=True
    ) as TTNClient:
        instance = TTNClient.return_value
        instance.fetch_data = AsyncMock(return_value=DATA)
        yield TTNClient
