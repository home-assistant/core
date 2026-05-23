"""Tests for Virtual Remote integration setup."""

from unittest.mock import patch

from homeassistant.components.virtual_remote import (
    _async_update_listener,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test setup forwards remote platform and unloads it."""
    with (
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            return_value=True,
        ) as mock_forward,
        patch.object(
            hass.config_entries,
            "async_unload_platforms",
            return_value=True,
        ) as mock_unload,
    ):
        assert await async_setup_entry(hass, config_entry)
        assert await async_unload_entry(hass, config_entry)

    mock_forward.assert_called_once_with(config_entry, ["remote"])
    mock_unload.assert_called_once_with(config_entry, ["remote"])


async def test_options_update_listener_reloads_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test options update listener reloads config entry."""
    with (
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            return_value=True,
        ),
        patch.object(
            hass.config_entries,
            "async_reload",
            return_value=None,
        ) as mock_reload,
    ):
        assert await async_setup_entry(hass, config_entry)
        await _async_update_listener(hass, config_entry)

    mock_reload.assert_called_once_with(config_entry.entry_id)
