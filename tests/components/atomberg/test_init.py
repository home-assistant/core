"""Tests for Atomberg setup and device handling."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.atomberg.api import (
    AtombergAuthError,
    AtombergConnectionError,
)
from homeassistant.components.atomberg.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

FULL_FAN = "fan.living_room"


@pytest.mark.usefixtures("mock_client")
async def test_setup_and_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the entry loads and unloads."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("mock_client")
async def test_devices_are_registered(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test fans, the water purifier and the lock are registered with their metadata."""
    await setup_integration(hass, mock_config_entry)

    def device(device_id: str) -> dr.DeviceEntry | None:
        return device_registry.async_get_device_by_identifier(
            (DOMAIN, device_id), mock_config_entry.entry_id
        )

    living_room = device("a4cf12abcdef")
    assert living_room is not None
    assert living_room.manufacturer == "Atomberg"
    assert living_room.model == "Renesa+"
    assert living_room.model_id == "I1"
    assert device("a4cf12123456") is not None
    assert device("a4cf12aa0001") is not None
    assert device("a4cf12999999") is not None


@pytest.mark.usefixtures("mock_client")
@pytest.mark.parametrize(
    ("entity_id", "present"),
    [
        ("fan.living_room", True),
        ("light.living_room_led", True),
        ("switch.living_room_sleep_mode", True),
        ("select.living_room_timer", True),
        ("fan.bedroom", True),
        ("light.bedroom_led", False),
        ("switch.bedroom_sleep_mode", False),
        ("select.bedroom_timer", False),
        ("fan.kitchen_water_purifier", False),
        ("fan.front_door", False),
        ("sensor.front_door_battery", True),
        ("button.front_door_generate_guest_pin", True),
        ("select.kitchen_water_purifier_purification_mode", True),
        ("number.kitchen_water_purifier_tds_threshold", True),
    ],
)
async def test_entities_follow_supported_commands(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    present: bool,
) -> None:
    """Test entities exist only for commands a device supports."""
    await setup_integration(hass, mock_config_entry)

    assert (hass.states.get(entity_id) is not None) is present


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        (AtombergConnectionError, ConfigEntryState.SETUP_RETRY),
        (AtombergAuthError, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_failures(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: type[Exception],
    state: ConfigEntryState,
) -> None:
    """Test setup failure handling for device list errors."""
    mock_client.async_get_devices.side_effect = exception

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is state


async def test_offline_device_unavailable(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test an offline device's entities become unavailable."""
    mock_client.async_get_states.return_value["a4cf12abcdef"]["is_online"] = False

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(FULL_FAN).state == STATE_UNAVAILABLE
    assert hass.states.get("fan.bedroom").state != STATE_UNAVAILABLE
