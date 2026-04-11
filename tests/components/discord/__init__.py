"""Tests for the Discord integration."""

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import nextcord

from homeassistant.components.discord.const import (
    CONF_CHANNEL_ID,
    DOMAIN,
    SUBENTRY_TYPE_CHANNEL,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TOKEN = "mock-bot-token"
BOT_NAME = "Mock Discord Bot"
BOT_ID = "1234567890"

CHANNEL_ID = 9876543210
CHANNEL_NAME = "general"

CONF_INPUT = {CONF_API_TOKEN: TOKEN}

CONF_DATA = {CONF_API_TOKEN: TOKEN}


def create_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add a fully configured Discord config entry to hass."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA,
        unique_id=BOT_ID,
        title=BOT_NAME,
        minor_version=1,
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_CHANNEL,
                unique_id=str(CHANNEL_ID),
                title=CHANNEL_NAME,
                data={CONF_CHANNEL_ID: CHANNEL_ID},
            )
        ],
    )
    entry.add_to_hass(hass)
    return entry


def mock_app_info() -> MagicMock:
    """Return a mock nextcord.AppInfo."""
    info = MagicMock(spec=nextcord.AppInfo)
    info.id = int(BOT_ID)
    info.name = BOT_NAME
    return info


@contextmanager
def patch_discord_login():
    """Patch nextcord.Client.login to succeed silently."""
    with patch(
        "homeassistant.components.discord.config_flow.nextcord.Client.login",
        new_callable=AsyncMock,
    ) as mock:
        yield mock


@contextmanager
def patch_discord_close():
    """Patch nextcord.Client.close."""
    with patch(
        "homeassistant.components.discord.config_flow.nextcord.Client.close",
        new_callable=AsyncMock,
    ) as mock:
        yield mock


@contextmanager
def mocked_discord_info():
    """Patch nextcord.Client.application_info to return mock app info."""
    with patch(
        "homeassistant.components.discord.config_flow.nextcord.Client.application_info",
        new_callable=AsyncMock,
        return_value=mock_app_info(),
    ) as mock:
        yield mock
