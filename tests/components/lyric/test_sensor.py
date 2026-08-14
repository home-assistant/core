"""Tests for the Honeywell Lyric sensor platform."""

from datetime import datetime
from unittest.mock import patch

import pytest

from homeassistant.components.lyric.const import DOMAIN
from homeassistant.components.lyric.sensor import get_datetime_from_future_time
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import MAC

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


@pytest.mark.usefixtures("mock_lyric")
async def test_accessory_links_to_thermostat_via_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test room sensors remain linked with a non-thermostat in the account."""
    with patch("homeassistant.components.lyric.PLATFORMS", [Platform.SENSOR]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    thermostat = device_registry.async_get_device_by_identifier(
        (dr.CONNECTION_NETWORK_MAC, MAC), mock_config_entry.entry_id
    )
    assert thermostat is not None

    accessory = device_registry.async_get_device_by_identifier(
        (f"{dr.CONNECTION_NETWORK_MAC}_room_accessory", f"{MAC}_room1_accessory1"),
        mock_config_entry.entry_id,
    )
    assert accessory is not None
    assert accessory.via_device_id == thermostat.id

    for sensor_key in (
        "room_temperature",
        "room_humidity",
        "room_average_temperature",
    ):
        assert (
            entity_registry.async_get_entity_id(
                Platform.SENSOR,
                DOMAIN,
                f"{MAC}_room1_acc1_{sensor_key}",
            )
            is not None
        )
