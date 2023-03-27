"""Test the imap entry initialization."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.imap import DOMAIN
from homeassistant.components.imap.errors import InvalidAuth, InvalidFolder
from homeassistant.core import HomeAssistant

from .test_config_flow import MOCK_CONFIG

from tests.common import MockConfigEntry


@pytest.mark.parametrize("imap_capabilities", [{"IDLE"}, set()], ids=["push", "poll"])
async def test_entry_startup_and_unload(
    hass: HomeAssistant, mock_imap_protocol: MagicMock
) -> None:
    """Test imap entry startup and unload with push and polling coordinator."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert await config_entry.async_unload(hass)


@pytest.mark.parametrize(
    "effect",
    [
        InvalidAuth,
        InvalidFolder,
        asyncio.TimeoutError,
    ],
)
async def test_entry_startup_fails(
    hass: HomeAssistant,
    mock_imap_protocol: MagicMock,
    effect: Exception,
) -> None:
    """Test imap entry startup fails on invalid auth or folder."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.imap.connect_to_server",
        side_effect=effect,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is False
