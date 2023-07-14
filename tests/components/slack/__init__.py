"""Tests for the Slack integration."""
from __future__ import annotations

import json

from homeassistant.components.slack.const import CONF_DEFAULT_CHANNEL, DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

AUTH_URL = "https://www.slack.com/api/auth.test"

TOKEN = "abc123"
TEAM_NAME = "Test Team"
TEAM_ID = "abc123def"

CONF_INPUT = {CONF_API_KEY: TOKEN, CONF_DEFAULT_CHANNEL: "test_channel"}

CONF_DATA = CONF_INPUT | {CONF_NAME: TEAM_NAME}


def create_entry(hass: HomeAssistant) -> ConfigEntry:
    """Add config entry in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA,
        unique_id=TEAM_ID,
    )
    entry.add_to_hass(hass)
    return entry


def mock_connection(
    aioclient_mock: AiohttpClientMocker, error: str | None = None
) -> None:
    """Mock connection."""
    if error is not None:
        if error == "invalid_auth":
            aioclient_mock.post(
                AUTH_URL,
                text=json.dumps({"ok": False, "error": "invalid_auth"}),
            )
        else:
            aioclient_mock.post(
                AUTH_URL,
                text=json.dumps({"ok": False, "error": "cannot_connect"}),
            )
    else:
        aioclient_mock.post(
            AUTH_URL,
            text=load_fixture("slack/auth_test.json"),
        )


async def async_init_integration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    skip_setup: bool = False,
    error: str | None = None,
) -> ConfigEntry:
    """Set up the Slack integration in Home Assistant."""
    entry = create_entry(hass)
    mock_connection(aioclient_mock, error)

    if not skip_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
