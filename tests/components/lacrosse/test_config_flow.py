"""Tests for the LaCrosse config flow."""

from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from homeassistant import config_entries
from homeassistant.components.lacrosse.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

RECEIVER_DATA = {
    "device": "/dev/ttyUSB0",
    "baud": 57600,
}
TEMPERATURE_SENSOR = {
    "id": 1,
    "type": "temperature",
    "expire_after": 300,
    "friendly_name": "Outdoor temperature",
}
HUMIDITY_SENSOR = {
    "id": 1,
    "type": "humidity",
    "friendly_name": "Outdoor humidity",
}
IMPORT_CONFIG = {
    "platform": "lacrosse",
    "device": "/dev/pts/6",
    "baud": 57600,
    "sensors": {
        "heating": {
            "type": "humidity",
            "id": 34,
        },
        "heating_temperature": {
            "name": "heating",
            "type": "temperature",
            "id": 34,
        },
        "heating_lacrosse_battery": {
            "name": "Heating battery",
            "type": "battery",
            "id": 34,
        },
        "livingroom_temperature": {
            "name": "Living room temperature",
            "type": "temperature",
            "id": 9,
        },
        "livingroom_lacrosse_battery": {
            "name": "Living room battery",
            "type": "battery",
            "id": 9,
        },
    },
}

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_user_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test configuring a receiver and its sensors."""
    with patch(
        "homeassistant.components.lacrosse.config_flow.uuid4",
        side_effect=[UUID(int=1), UUID(int=2)],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], RECEIVER_DATA
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "sensor"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEMPERATURE_SENSOR
        )
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "add_sensor"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "sensor"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "sensor"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], HUMIDITY_SENSOR
        )
        assert result["type"] is FlowResultType.MENU

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"next_step_id": "finish"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "/dev/ttyUSB0"
    assert result["data"] == {
        **RECEIVER_DATA,
        "sensors": {
            "1_temperature": {
                **TEMPERATURE_SENSOR,
                "unique_id": "00000000000000000000000000000001",
            },
            "1_humidity": {
                **HUMIDITY_SENSOR,
                "unique_id": "00000000000000000000000000000002",
            },
        },
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_duplicate_receiver(hass: HomeAssistant) -> None:
    """Test that a receiver can only be configured once."""
    MockConfigEntry(domain=DOMAIN, data=RECEIVER_DATA).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], RECEIVER_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test importing a receiver and sensors from YAML."""
    with patch(
        "homeassistant.components.lacrosse.config_flow.uuid4",
        side_effect=[UUID(int=i) for i in range(1, 6)],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=IMPORT_CONFIG,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "/dev/pts/6"
    assert result["data"] == {
        "device": "/dev/pts/6",
        "baud": 57600,
        "datarate": None,
        "frequency": None,
        "led": None,
        "toggle_interval": None,
        "toggle_mask": None,
        "sensors": {
            "heating": {
                "id": 34,
                "type": "humidity",
                "friendly_name": "heating",
                "unique_id": "00000000000000000000000000000001",
            },
            "heating_temperature": {
                "id": 34,
                "type": "temperature",
                "friendly_name": "heating",
                "unique_id": "00000000000000000000000000000002",
            },
            "heating_lacrosse_battery": {
                "id": 34,
                "type": "battery",
                "friendly_name": "Heating battery",
                "unique_id": "00000000000000000000000000000003",
            },
            "livingroom_temperature": {
                "id": 9,
                "type": "temperature",
                "friendly_name": "Living room temperature",
                "unique_id": "00000000000000000000000000000004",
            },
            "livingroom_lacrosse_battery": {
                "id": 9,
                "type": "battery",
                "friendly_name": "Living room battery",
                "unique_id": "00000000000000000000000000000005",
            },
        },
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_duplicate_sensor(hass: HomeAssistant) -> None:
    """Test that the same sensor type cannot be added twice."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], RECEIVER_DATA
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEMPERATURE_SENSOR
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "sensor"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEMPERATURE_SENSOR
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sensor"
    assert result["errors"] == {"base": "sensor_already_configured"}
