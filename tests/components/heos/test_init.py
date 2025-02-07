"""Tests for the init module."""

from typing import cast
from unittest.mock import Mock

from pyheos import HeosError, HeosOptions, SignalHeosEvent, SignalType
import pytest

from homeassistant.components.heos.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import MockHeos

from tests.common import MockConfigEntry


async def test_async_setup_entry_loads_platforms(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
) -> None:
    """Test load connects to heos, retrieves players, and loads platforms."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("media_player.test_player") is not None
    assert controller.connect.call_count == 1
    assert controller.get_players.call_count == 1
    assert controller.get_favorites.call_count == 1
    assert controller.get_input_sources.call_count == 1
    controller.disconnect.assert_not_called()


async def test_async_setup_entry_with_options_loads_platforms(
    hass: HomeAssistant,
    config_entry_options: MockConfigEntry,
    controller: MockHeos,
    new_mock: Mock,
) -> None:
    """Test load connects to heos with options, retrieves players, and loads platforms."""
    config_entry_options.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry_options.entry_id)

    # Assert options passed and methods called
    assert config_entry_options.state is ConfigEntryState.LOADED
    options = cast(HeosOptions, new_mock.call_args[0][0])
    assert options.host == config_entry_options.data[CONF_HOST]
    assert options.credentials is not None
    assert options.credentials.username == config_entry_options.options[CONF_USERNAME]
    assert options.credentials.password == config_entry_options.options[CONF_PASSWORD]
    assert controller.connect.call_count == 1
    assert controller.get_players.call_count == 1
    assert controller.get_favorites.call_count == 1
    assert controller.get_input_sources.call_count == 1
    controller.disconnect.assert_not_called()


async def test_async_setup_entry_auth_failure_starts_reauth(
    hass: HomeAssistant,
    config_entry_options: MockConfigEntry,
    controller: MockHeos,
) -> None:
    """Test load with auth failure starts reauth, loads platforms."""
    config_entry_options.add_to_hass(hass)

    # Simulates what happens when the controller can't sign-in during connection
    async def connect_send_auth_failure() -> None:
        controller.mock_set_signed_in_username(None)
        await controller.dispatcher.wait_send(
            SignalType.HEOS_EVENT, SignalHeosEvent.USER_CREDENTIALS_INVALID
        )

    controller.connect.side_effect = connect_send_auth_failure

    assert await hass.config_entries.async_setup(config_entry_options.entry_id)

    # Assert entry loaded and reauth flow started
    assert controller.connect.call_count == 1
    assert controller.get_favorites.call_count == 0
    controller.disconnect.assert_not_called()
    assert config_entry_options.state is ConfigEntryState.LOADED
    assert any(
        config_entry_options.async_get_active_flows(hass, sources={SOURCE_REAUTH})
    )


async def test_async_setup_entry_not_signed_in_loads_platforms(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup does not retrieve favorites when not logged in."""
    config_entry.add_to_hass(hass)
    controller.mock_set_signed_in_username(None)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    assert controller.connect.call_count == 1
    assert controller.get_players.call_count == 1
    assert controller.get_favorites.call_count == 0
    assert controller.get_input_sources.call_count == 1
    controller.disconnect.assert_not_called()
    assert (
        "The HEOS System is not logged in: Enter credentials in the integration options to access favorites and streaming services"
        in caplog.text
    )


async def test_async_setup_entry_connect_failure(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Connection failure raises ConfigEntryNotReady."""
    config_entry.add_to_hass(hass)
    controller.connect.side_effect = HeosError()
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert controller.connect.call_count == 1
    assert controller.disconnect.call_count == 1
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_async_setup_entry_player_failure(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Failure to retrieve players raises ConfigEntryNotReady."""
    config_entry.add_to_hass(hass)
    controller.get_players.side_effect = HeosError()
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert controller.connect.call_count == 1
    assert controller.disconnect.call_count == 1
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_async_setup_entry_favorites_failure(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Failure to retrieve favorites loads."""
    config_entry.add_to_hass(hass)
    controller.get_favorites.side_effect = HeosError()
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED


async def test_async_setup_entry_inputs_failure(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Failure to retrieve inputs loads."""
    config_entry.add_to_hass(hass)
    controller.get_input_sources.side_effect = HeosError()
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED


async def test_unload_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test entries are unloaded correctly."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert controller.disconnect.call_count == 1


async def test_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test device information populates correctly."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    device = device_registry.async_get_device({(DOMAIN, "1")})
    assert device is not None
    assert device.manufacturer == "HEOS"
    assert device.model == "Drive HS2"
    assert device.name == "Test Player"
    assert device.serial_number == "123456"
    assert device.sw_version == "1.0.0"
    device = device_registry.async_get_device({(DOMAIN, "2")})
    assert device is not None
    assert device.manufacturer == "HEOS"
    assert device.model == "Speaker"


async def test_device_id_migration(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test that legacy non-string device identifiers are migrated to strings."""
    config_entry.add_to_hass(hass)
    # Create a device with a legacy identifier
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, 1)},  # type: ignore[arg-type]
    )
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("Other", 1)},  # type: ignore[arg-type]
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    assert device_registry.async_get_device({("Other", 1)}) is not None  # type: ignore[arg-type]
    assert device_registry.async_get_device({(DOMAIN, 1)}) is None  # type: ignore[arg-type]
    assert device_registry.async_get_device({(DOMAIN, "1")}) is not None
