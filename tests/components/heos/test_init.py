"""Tests for the init module."""

from typing import cast

from pyheos import (
    CommandFailedError,
    Heos,
    HeosError,
    HeosOptions,
    SignalHeosEvent,
    SignalType,
    const,
)
import pytest

from homeassistant.components.heos.const import (
    DOMAIN,
    SERVICE_SIGN_IN,
    SERVICE_SIGN_OUT,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_async_setup_returns_true(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test component setup and services registered."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    assert hass.services.has_service(DOMAIN, SERVICE_SIGN_IN)
    assert hass.services.has_service(DOMAIN, SERVICE_SIGN_OUT)


async def test_async_setup_entry_and_async_unload_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: Heos
) -> None:
    """Test load and unload of the config entry."""
    # Load
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED
    assert controller.connect.call_count == 1
    assert controller.get_players.call_count == 1
    assert controller.get_favorites.call_count == 1
    assert controller.get_input_sources.call_count == 1
    controller.disconnect.assert_not_called()

    # Unload
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert controller.disconnect.call_count == 1


async def test_async_setup_entry_with_options_loads_platforms(
    hass: HomeAssistant,
    config_entry_options: MockConfigEntry,
    controller: Heos,
) -> None:
    """Test load connects to heos with options, retrieves players, and loads platforms."""
    config_entry_options.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry_options.entry_id)
    assert config_entry_options.state is ConfigEntryState.LOADED
    # Assert options passed and methods called
    options = cast(HeosOptions, controller.new_mock.call_args[0][0])
    assert options.host == config_entry_options.data[CONF_HOST]
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
    controller: Heos,
) -> None:
    """Test load with auth failure starts reauth, loads platforms."""
    config_entry_options.add_to_hass(hass)

    # Simulates what happens when the controller can't sign-in during connection
    async def connect_send_auth_failure() -> None:
        controller._signed_in_username = None
        controller.dispatcher.send(
            SignalType.HEOS_EVENT, SignalHeosEvent.USER_CREDENTIALS_INVALID
        )

    controller.connect.side_effect = connect_send_auth_failure

    assert await hass.config_entries.async_setup(config_entry_options.entry_id)
    assert config_entry_options.state is ConfigEntryState.LOADED

    # Assert entry loaded and reauth flow started
    assert controller.connect.call_count == 1
    assert controller.get_favorites.call_count == 0
    controller.disconnect.assert_not_called()
    assert any(
        config_entry_options.async_get_active_flows(hass, sources=[SOURCE_REAUTH])
    )


async def test_async_setup_entry_not_signed_in_loads_platforms(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: Heos,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup does not retrieve favorites when not logged in."""
    controller._signed_in_username = None
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED
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
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: Heos
) -> None:
    """Connection failure raises ConfigEntryNotReady."""
    controller.connect.side_effect = HeosError()
    config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert controller.connect.call_count == 1


async def test_async_setup_entry_player_failure(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: Heos
) -> None:
    """Failure to retrieve players/sources raises ConfigEntryNotReady."""
    controller.get_players.side_effect = HeosError()
    config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert controller.connect.call_count == 1
    assert controller.disconnect.call_count == 2  # Temp


async def test_update_sources_retry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: Heos,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update sources retries on failures to max attempts."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    controller.get_favorites.reset_mock()
    source_manager = config_entry.runtime_data.source_manager
    source_manager.retry_delay = 0
    source_manager.max_retry_attempts = 1
    controller.get_favorites.side_effect = CommandFailedError("Test", "test", 0)
    await controller.dispatcher.wait_send(
        SignalType.CONTROLLER_EVENT, const.EVENT_SOURCES_CHANGED, {}
    )
    assert "Unable to update sources" in caplog.text
    assert controller.get_favorites.call_count == 2


async def test_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test device information populates correctly."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    device = device_registry.async_get_device({(DOMAIN, "1")})
    assert device.manufacturer == "HEOS"
    assert device.model == "Drive HS2"
    assert device.name == "Test Player"
    assert device.serial_number == "123456"
    assert device.sw_version == "1.0.0"
    device = device_registry.async_get_device({(DOMAIN, "2")})
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
        config_entry_id=config_entry.entry_id, identifiers={(DOMAIN, 1)}
    )
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={("Other", 1)}
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    assert device_registry.async_get_device({("Other", 1)}) is not None
    assert device_registry.async_get_device({(DOMAIN, 1)}) is None
    assert device_registry.async_get_device({(DOMAIN, "1")}) is not None
