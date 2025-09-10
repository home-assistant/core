"""TFA.me station integration: test of text.py."""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.a_tfa_me_1.const import (
    DEVICE_MAPPING,
    ICON_MAPPING,
    TIMEOUT_MAPPING,
)
from homeassistant.components.a_tfa_me_1.text import TFAmeTextEntity


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator with dummy data."""
    coordinator = AsyncMock()
    coordinator.host = "192.168.1.10"
    coordinator.multiple_entities = False  # True
    now_ts = int(datetime.now().timestamp())
    coordinator.data = {
        "sensor.a6f169ad1_lowbatt": {
            "gateway_id": "017654321",
            "sensor_name": "A6F169AD1",
            "measurement": "lowbatt",
            "value": 1,
            "text": "Yes",
            "ts": now_ts,
            "timestamp": "2025-08-25T15:00:00Z",
        },
        "sensor.a01234567_temperature": {  # old timestamp triggers timeout
            "gateway_id": "017654321",
            "sensor_name": "A01234567",
            "measurement": "temperature",
            "value": 20.0,
            "text": "20°C",
            "ts": now_ts - 1000000,
            "timestamp": "2025-08-24T12:00:00Z",
        },
        "sensor.a6f169ad1_lowbatt_txt": {  # invalid data
            "gateway_id": "017654321",
            "sensor_name": "A6F169AD1",
            "measurement": "lowbatt_text",
            "value": None,
            "text": None,
            "ts": "invalid",
            "timestamp": "invalid",
        },
        "sensor.a2ffffffb_wind_dir": {  # wind wind direction as value
            "gateway_id": "017654321",
            "sensor_name": "A2FFFFFFB",
            "measurement": "wind_dir",
            "value": 0,
            "text": "N",
            "ts": now_ts,
            "timestamp": "2025-08-24T12:00:00Z",
        },
        "sensor.a2ffffffb_wind_dir_txt": {  # wind direction as text
            "gateway_id": "017654321",
            "sensor_name": "A2FFFFFFB",
            "measurement": "wind_direction_text",
            "value": 0,
            "text": "N",
            "ts": now_ts,
            "timestamp": "2025-08-24T12:00:00Z",
        },
        "sensor.a2ffffffc_wind_dir": {  # wind
            "gateway_id": "017654321",
            "sensor_name": "A2FFFFFFC",
            "value": 0,
            "text": "N",
            "ts": now_ts,
            "timestamp": "2025-08-24T12:00:00Z",
        },
    }
    return coordinator


@pytest.fixture
def text_entity(mock_coordinator):
    """Create TFAmeTextEntity for entity sensor.a6f169ad1_lowbatt."""
    return TFAmeTextEntity(
        mock_coordinator, sensor_id="A6F169AD1", entity_id="sensor.a6f169ad1_lowbatt"
    )


@pytest.fixture
def text_entity_2(mock_coordinator):
    """Create TFAmeTextEntity for entity sensor.a2ffffffc_wind_dir."""
    return TFAmeTextEntity(
        mock_coordinator, sensor_id="A2FFFFFFC", entity_id="sensor.a2ffffffc_wind_dir"
    )


@pytest.mark.asyncio
async def test_native_value_valid(text_entity) -> None:
    """native_value returns correct text if timestamp valid."""
    value = text_entity.native_value
    assert value == "Yes"


def test_native_value_timeout(mock_coordinator) -> None:
    """native_value returns None if timestamp exceeds timeout."""
    entity = TFAmeTextEntity(
        mock_coordinator,
        sensor_id="A01234567",
        entity_id="sensor.a01234567_temperature",
    )
    assert entity.native_value is None


def test_native_value_invalid(mock_coordinator) -> None:
    """native_value returns None on invalid data."""
    entity = TFAmeTextEntity(
        mock_coordinator,
        sensor_id="C00000000",
        entity_id="sensor.a6f169ad1_lowbatt_txt",
    )
    assert entity.native_value is None


def test_unique_id(text_entity) -> None:
    """Unique ID returns correct format."""
    assert text_entity.unique_id == "tfame_sensor.a6f169ad1_lowbatt"


def test_name_property(text_entity) -> None:
    """Name property returns correct string."""
    assert text_entity.name == "A6F169AD1 Lowbatt"
    assert text_entity.measurement_name == "lowbatt"


def test_extra_state_attributes(text_entity) -> None:
    """extra_state_attributes returns correct dictionary."""
    attrs = text_entity.extra_state_attributes
    assert attrs["sensor_name"] == "A6F169AD1"
    assert attrs["measurement"] == "lowbatt"
    assert attrs["icon"] == text_entity._attr_icon


def test_measurement_missing(text_entity_2) -> None:
    """Test missing measurement entry."""
    assert text_entity_2.measure_name == ""
    assert text_entity_2.name == "None"
    assert text_entity_2.measurement_name is None

    # Attribute(s) missing
    attrs = text_entity_2.extra_state_attributes
    assert attrs == {}


def test_format_string_helpers(mock_coordinator) -> None:
    """Test format_string_tfa_id and format_string_tfa_type."""
    entity = TFAmeTextEntity(
        mock_coordinator, sensor_id="A6F169AD1", entity_id="sensor.a6f169ad1_lowbatt"
    )
    id_str = entity.format_string_tfa_id("A6F169AD1", "gw01", True)
    assert id_str.startswith("TFA.me A6F-169-AD1")
    type_str = entity.format_string_tfa_type("A6F169AD1")
    assert type_str in DEVICE_MAPPING.values() or type_str == "?"


def test_get_icon_lowbatt_text(mock_coordinator) -> None:
    """Icon for lowbatt_text."""
    entity = TFAmeTextEntity(
        mock_coordinator,
        sensor_id="A6F169AD1",
        entity_id="sensor.a01234567_temperature",
    )
    icon = entity.get_icon("lowbatt_txt", 0)
    assert icon in ICON_MAPPING["lowbatt"].values() or icon == "mdi:help-circle"
    assert entity.icon == "mdi:help-circle"

    # Invalid values
    icon = entity.get_icon("lowbatt_txt", "hello world")
    assert icon == "mdi:help-circle"
    icon = entity.get_icon("lowbatt_txt", None)
    assert icon == "mdi:help-circle"


def test_get_icon_wind_direction(mock_coordinator) -> None:
    """Icon for wind_direction_text values 0-15 and None."""
    entity = TFAmeTextEntity(
        mock_coordinator, sensor_id="A2FFFFFFB", entity_id="sensor.a2ffffffb_wind_dir"
    )
    for val in range(16):
        icon = entity.get_wind_direction_icon(val)
        assert icon.startswith("mdi:")
    assert entity.get_wind_direction_icon(None) == "mdi:compass-outline"
    assert entity.get_wind_direction_icon(16) == "mdi:compass-outline"

    entity_2 = TFAmeTextEntity(
        mock_coordinator,
        sensor_id="A2FFFFFFB",
        entity_id="sensor.a2ffffffb_wind_dir_txt",
    )
    assert entity_2.native_value == "N"


def test_get_timeout_known_unknown(mock_coordinator) -> None:
    """Test get_timeout with known and unknown sensor_id."""
    entity = TFAmeTextEntity(
        mock_coordinator, sensor_id="A6F169AD1", entity_id="sensor.a6f169ad1_lowbatt"
    )
    assert entity.get_timeout("A6F169AD1") == TIMEOUT_MAPPING.get("A6", 0)
    assert entity.get_timeout("ZZZZ") == 0


@pytest.mark.asyncio
async def test_async_update_calls_coordinator(text_entity) -> None:
    """async_update calls coordinator async_request_refresh."""
    await text_entity.async_update()
    text_entity.coordinator.async_request_refresh.assert_awaited_once()
