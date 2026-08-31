"""Tests for the LaCrosse config flow."""

from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from homeassistant import config_entries
from homeassistant.components.lacrosse.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry

RECEIVER_DATA = {
    "device": "/dev/ttyUSB0",
    "baud": 57600,
}
TEMPERATURE_SENSOR = {
    "id": 1,
    "temperature": True,
    "humidity": False,
    "battery": False,
    "expire_after": 300,
    "friendly_name": "Outdoor temperature",
}
HUMIDITY_SENSOR = {
    "id": 1,
    "temperature": False,
    "humidity": True,
    "battery": False,
    "friendly_name": "Outdoor humidity",
}
ALL_TYPES_SENSOR = {
    "id": 2,
    "temperature": True,
    "humidity": True,
    "battery": True,
    "friendly_name": "Bedroom",
}
BATTERY_ONLY_SENSOR = {
    "id": 3,
    "temperature": False,
    "humidity": False,
    "battery": True,
}
MULTI_SENSOR_DATA = {
    **RECEIVER_DATA,
    "sensors": {
        "1_temperature": {
            "id": 1,
            "type": "temperature",
            "friendly_name": "Outdoor temperature",
            "unique_id": "00000000000000000000000000000001",
        },
        "1_humidity": {
            "id": 1,
            "type": "humidity",
            "friendly_name": "Outdoor humidity",
            "unique_id": "00000000000000000000000000000002",
        },
        "2_temperature": {
            "id": 2,
            "type": "temperature",
            "friendly_name": "Bedroom",
            "unique_id": "00000000000000000000000000000003",
        },
    },
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
                "id": 1,
                "type": "temperature",
                "expire_after": 300,
                "friendly_name": "Outdoor temperature",
                "unique_id": "00000000000000000000000000000001",
            },
            "1_humidity": {
                "id": 1,
                "type": "humidity",
                "friendly_name": "Outdoor humidity",
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


async def test_multiple_types_sensor(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that checking several types creates a sensor for each of them."""
    with patch(
        "homeassistant.components.lacrosse.config_flow.uuid4",
        side_effect=[UUID(int=1), UUID(int=2), UUID(int=3)],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], RECEIVER_DATA
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], ALL_TYPES_SENSOR
        )
        assert result["type"] is FlowResultType.MENU

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"next_step_id": "finish"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["sensors"] == {
        "2_battery": {
            "id": 2,
            "type": "battery",
            "friendly_name": "Bedroom",
            "unique_id": "00000000000000000000000000000001",
        },
        "2_humidity": {
            "id": 2,
            "type": "humidity",
            "friendly_name": "Bedroom",
            "unique_id": "00000000000000000000000000000002",
        },
        "2_temperature": {
            "id": 2,
            "type": "temperature",
            "friendly_name": "Bedroom",
            "unique_id": "00000000000000000000000000000003",
        },
    }


async def test_reconfigure_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test reconfiguring a receiver to add another sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            **RECEIVER_DATA,
            "sensors": {
                "1_temperature": {
                    "id": 1,
                    "type": "temperature",
                    "friendly_name": "Outdoor temperature",
                    "unique_id": "00000000000000000000000000000001",
                },
            },
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.lacrosse.config_flow.uuid4",
        side_effect=[UUID(int=2), UUID(int=3), UUID(int=4)],
    ):
        result = await entry.start_reconfigure_flow(hass)
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "reconfigure"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "sensor"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "sensor"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], ALL_TYPES_SENSOR
        )
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "add_sensor"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"next_step_id": "finish"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["sensors"] == {
        "1_temperature": {
            "id": 1,
            "type": "temperature",
            "friendly_name": "Outdoor temperature",
            "unique_id": "00000000000000000000000000000001",
        },
        "2_battery": {
            "id": 2,
            "type": "battery",
            "friendly_name": "Bedroom",
            "unique_id": "00000000000000000000000000000002",
        },
        "2_humidity": {
            "id": 2,
            "type": "humidity",
            "friendly_name": "Bedroom",
            "unique_id": "00000000000000000000000000000003",
        },
        "2_temperature": {
            "id": 2,
            "type": "temperature",
            "friendly_name": "Bedroom",
            "unique_id": "00000000000000000000000000000004",
        },
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reconfigure_flow_duplicate_sensor(hass: HomeAssistant) -> None:
    """Test that reconfigure refuses to add an already configured sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            **RECEIVER_DATA,
            "sensors": {
                "1_temperature": {
                    "id": 1,
                    "type": "temperature",
                    "friendly_name": "Outdoor temperature",
                    "unique_id": "00000000000000000000000000000001",
                },
            },
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "sensor"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEMPERATURE_SENSOR
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sensor"
    assert result["errors"] == {"base": "sensor_already_configured"}


async def test_change_sensor_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test changing the ID a sensor reports after a battery replacement."""
    entry = MockConfigEntry(domain=DOMAIN, data=MULTI_SENSOR_DATA)
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "/dev/ttyUSB0_1")},
    )

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "change_id"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "change_id"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"id": "1", "new_id": 7}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["sensors"] == {
        "7_temperature": {
            "id": 7,
            "type": "temperature",
            "friendly_name": "Outdoor temperature",
            "unique_id": "00000000000000000000000000000001",
        },
        "7_humidity": {
            "id": 7,
            "type": "humidity",
            "friendly_name": "Outdoor humidity",
            "unique_id": "00000000000000000000000000000002",
        },
        "2_temperature": {
            "id": 2,
            "type": "temperature",
            "friendly_name": "Bedroom",
            "unique_id": "00000000000000000000000000000003",
        },
    }
    assert device_registry.async_get(device.id).identifiers == {
        (DOMAIN, "/dev/ttyUSB0_7")
    }


async def test_change_sensor_id_duplicate(hass: HomeAssistant) -> None:
    """Test that a sensor ID cannot be changed to an already configured one."""
    entry = MockConfigEntry(domain=DOMAIN, data=MULTI_SENSOR_DATA)
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "change_id"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"id": "1", "new_id": 2}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "change_id"
    assert result["errors"] == {"base": "sensor_already_configured"}
    assert entry.data == MULTI_SENSOR_DATA


async def test_remove_sensor(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test removing a sensor and its device."""
    entry = MockConfigEntry(domain=DOMAIN, data=MULTI_SENSOR_DATA)
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "/dev/ttyUSB0_1")},
    )

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "remove_sensor"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "remove_sensor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"id": "1"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["sensors"] == {
        "2_temperature": {
            "id": 2,
            "type": "temperature",
            "friendly_name": "Bedroom",
            "unique_id": "00000000000000000000000000000003",
        },
    }
    assert device_registry.async_get(device.id) is None


async def test_value_type_required(hass: HomeAssistant) -> None:
    """Test that temperature or humidity has to be selected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], RECEIVER_DATA
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], BATTERY_ONLY_SENSOR
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sensor"
    assert result["errors"] == {"base": "value_type_required"}
