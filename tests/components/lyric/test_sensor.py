"""Tests for the Honeywell Lyric sensor platform."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.lyric.const import DOMAIN
from homeassistant.components.lyric.sensor import get_datetime_from_future_time
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


def test_get_datetime_from_future_time_none() -> None:
    """Test that None input returns None instead of raising."""
    assert get_datetime_from_future_time(None) is None


def test_get_datetime_from_future_time_invalid() -> None:
    """Test that an unparsable time string returns None."""
    assert get_datetime_from_future_time("not_a_time") is None


def test_get_datetime_from_future_time_valid() -> None:
    """Test that a valid time string returns a datetime."""
    result = get_datetime_from_future_time("13:30:00")
    assert isinstance(result, datetime)


@pytest.mark.usefixtures("setup_credentials")
async def test_room_sensors_created_regardless_of_device_id_prefix(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_lyric_mixed_devices: MagicMock,
) -> None:
    """Room/accessory sensors are created for supported devices whether or not their ID starts with LCC.

    An unsupported device (GetPriorityFailed 400) shouldn't get room
    sensors, but must not block setup or the other devices' sensors either.
    """
    with patch("homeassistant.components.lyric.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    lcc_room_sensor = hass.states.get(
        entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, "AABBCC000001_room0_acc0_room_temperature"
        )
    )
    assert lcc_room_sensor.state == "22.5"

    non_lcc_room_sensor = hass.states.get(
        entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, "AABBCC000002_room0_acc0_room_temperature"
        )
    )
    assert non_lcc_room_sensor.state == "24.5"

    assert (
        entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, "AABBCC000003_room0_acc0_room_temperature"
        )
        is None
    )

    unsupported_device_sensor = hass.states.get(
        entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, "AABBCC000003_indoor_temperature"
        )
    )
    assert unsupported_device_sensor.state == "21.5"
