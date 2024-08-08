"""Tests for the init module."""

import asyncio
from unittest.mock import Mock, patch

from pyheos import CommandFailedError, HeosError, const
import pytest

from homeassistant.components.heos import (
    ControllerManager,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.heos.const import (
    DATA_CONTROLLER_MANAGER,
    DATA_SOURCE_MANAGER,
    DOMAIN,
)
from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.setup import async_setup_component


async def test_async_setup_creates_entry(hass: HomeAssistant, config) -> None:
    """Test component setup creates entry from config."""
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.title == "Controller (127.0.0.1)"
    assert entry.data == {CONF_HOST: "127.0.0.1"}
    assert entry.unique_id == DOMAIN


async def test_async_setup_updates_entry(
    hass: HomeAssistant, config_entry, config, controller
) -> None:
    """Test component setup updates entry from config."""
    config[DOMAIN][CONF_HOST] = "127.0.0.2"
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.title == "Controller (127.0.0.2)"
    assert entry.data == {CONF_HOST: "127.0.0.2"}
    assert entry.unique_id == DOMAIN


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
    assert hass.data[DOMAIN][DATA_CONTROLLER_MANAGER].controller == controller
    assert hass.data[DOMAIN][MEDIA_PLAYER_DOMAIN] == controller.players
    assert hass.data[DOMAIN][DATA_SOURCE_MANAGER].favorites == favorites
    assert hass.data[DOMAIN][DATA_SOURCE_MANAGER].inputs == input_sources


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
    assert hass.data[DOMAIN][DATA_CONTROLLER_MANAGER].controller == controller
    assert hass.data[DOMAIN][MEDIA_PLAYER_DOMAIN] == controller.players
    assert hass.data[DOMAIN][DATA_SOURCE_MANAGER].favorites == {}
    assert hass.data[DOMAIN][DATA_SOURCE_MANAGER].inputs == input_sources
    assert (
        "127.0.0.1 is not logged in to a HEOS account and will be unable to retrieve "
        "HEOS favorites: Use the 'heos.sign_in' service to sign-in to a HEOS account"
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
    hass.data[DOMAIN] = {DATA_CONTROLLER_MANAGER: controller_manager}
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
    source_manager = hass.data[DOMAIN][DATA_SOURCE_MANAGER]
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
