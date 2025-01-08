"""Tests for the init module."""

import asyncio
from typing import cast
from unittest.mock import Mock, patch

from pyheos import CommandFailedError, HeosError, const
import pytest

from homeassistant.components.heos import (
    ControllerManager,
    HeosOptions,
    HeosRuntimeData,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.heos.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_async_setup_returns_true(
    hass: HomeAssistant, config_entry, config
) -> None:
    """Test component setup from config."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0] == config_entry


async def test_async_setup_no_config_returns_true(
    hass: HomeAssistant, config_entry
) -> None:
    """Test component setup from entry only."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0] == config_entry


async def test_async_setup_entry_loads_platforms(
    hass: HomeAssistant, config_entry, controller, input_sources, favorites
) -> None:
    """Test load connects to heos, retrieves players, and loads platforms."""
    config_entry.add_to_hass(hass)
    with patch.object(
        hass.config_entries, "async_forward_entry_setups"
    ) as forward_mock:
        assert await async_setup_entry(hass, config_entry)
        # Assert platforms loaded
        await hass.async_block_till_done()
        assert forward_mock.call_count == 1
        assert controller.connect.call_count == 1
        assert controller.get_players.call_count == 1
        assert controller.get_favorites.call_count == 1
        assert controller.get_input_sources.call_count == 1
        controller.disconnect.assert_not_called()


async def test_async_setup_entry_with_options_loads_platforms(
    hass: HomeAssistant,
    config_entry_options,
    config,
    controller,
    input_sources,
    favorites,
) -> None:
    """Test load connects to heos with options, retrieves players, and loads platforms."""
    config_entry_options.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    # Assert options passed and methods called
    assert config_entry_options.state is ConfigEntryState.LOADED
    options = cast(HeosOptions, controller.call_args[0][0])
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
    controller: Mock,
) -> None:
    """Test load with auth failure starts reauth, loads platforms."""
    config_entry_options.add_to_hass(hass)

    # Simulates what happens when the controller can't sign-in during connection
    async def connect_send_auth_failure() -> None:
        controller.is_signed_in = False
        controller.signed_in_username = None
        controller.dispatcher.send(
            const.SIGNAL_HEOS_EVENT, const.EVENT_USER_CREDENTIALS_INVALID
        )

    controller.connect.side_effect = connect_send_auth_failure

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # Assert entry loaded and reauth flow started
    assert controller.connect.call_count == 1
    assert controller.get_favorites.call_count == 0
    controller.disconnect.assert_not_called()
    assert config_entry_options.state is ConfigEntryState.LOADED
    assert any(
        config_entry_options.async_get_active_flows(hass, sources=[SOURCE_REAUTH])
    )


async def test_async_setup_entry_not_signed_in_loads_platforms(
    hass: HomeAssistant,
    config_entry,
    controller,
    input_sources,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup does not retrieve favorites when not logged in."""
    config_entry.add_to_hass(hass)
    controller.is_signed_in = False
    controller.signed_in_username = None
    with patch.object(
        hass.config_entries, "async_forward_entry_setups"
    ) as forward_mock:
        assert await async_setup_entry(hass, config_entry)
        # Assert platforms loaded
        await hass.async_block_till_done()
        assert forward_mock.call_count == 1
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
    hass: HomeAssistant, config_entry, controller
) -> None:
    """Connection failure raises ConfigEntryNotReady."""
    config_entry.add_to_hass(hass)
    controller.connect.side_effect = HeosError()
    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, config_entry)
    assert controller.connect.call_count == 1
    assert controller.disconnect.call_count == 1
    controller.connect.reset_mock()
    controller.disconnect.reset_mock()


async def test_async_setup_entry_player_failure(
    hass: HomeAssistant, config_entry, controller
) -> None:
    """Failure to retrieve players/sources raises ConfigEntryNotReady."""
    config_entry.add_to_hass(hass)
    controller.get_players.side_effect = HeosError()
    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, config_entry)
    assert controller.connect.call_count == 1
    assert controller.disconnect.call_count == 1
    controller.connect.reset_mock()
    controller.disconnect.reset_mock()


async def test_unload_entry(hass: HomeAssistant, config_entry, controller) -> None:
    """Test entries are unloaded correctly."""
    controller_manager = Mock(ControllerManager)
    config_entry.runtime_data = HeosRuntimeData(controller_manager, None, None, {})

    with patch.object(
        hass.config_entries, "async_forward_entry_unload", return_value=True
    ) as unload:
        assert await async_unload_entry(hass, config_entry)
        await hass.async_block_till_done()
        assert controller_manager.disconnect.call_count == 1
        assert unload.call_count == 1
    assert DOMAIN not in hass.data


async def test_update_sources_retry(
    hass: HomeAssistant,
    config_entry,
    config,
    controller,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update sources retries on failures to max attempts."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, config)
    controller.get_favorites.reset_mock()
    controller.get_input_sources.reset_mock()
    source_manager = config_entry.runtime_data.source_manager
    source_manager.retry_delay = 0
    source_manager.max_retry_attempts = 1
    controller.get_favorites.side_effect = CommandFailedError("Test", "test", 0)
    controller.dispatcher.send(
        const.SIGNAL_CONTROLLER_EVENT, const.EVENT_SOURCES_CHANGED, {}
    )
    # Wait until it's finished
    while "Unable to update sources" not in caplog.text:
        await asyncio.sleep(0.1)
    assert controller.get_favorites.call_count == 2
