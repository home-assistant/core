"""Tests for Atomberg setup and device handling."""

from unittest.mock import AsyncMock

from atomberg_api import AtombergAuthError, AtombergConnectionError, AtombergError
import pytest
from pytest_homeassistant.common import MockConfigEntry

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
    """Test fans are registered with their metadata."""
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


@pytest.mark.usefixtures("mock_client")
async def test_only_fans_are_created(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a fan entity exists for each fan and nothing else is created."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("fan.living_room") is not None
    assert hass.states.get("fan.bedroom") is not None
    assert len(hass.states.async_entity_ids()) == 2


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


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        (AtombergConnectionError, ConfigEntryState.SETUP_RETRY),
        (AtombergError, ConfigEntryState.SETUP_RETRY),
        (AtombergAuthError, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_first_refresh_failures(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: type[Exception],
    state: ConfigEntryState,
) -> None:
    """Test state polling errors during setup."""
    mock_client.async_get_states.side_effect = exception

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is state


async def test_device_list_generic_error(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test an unexpected device list error makes setup retry."""
    mock_client.async_get_devices.side_effect = AtombergError("bad")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
