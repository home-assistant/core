"""Test Agent DVR integration."""

from urllib.parse import quote

import aiohttp

from homeassistant.components.agent_dvr.const import DOMAIN, SERVER_URL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from . import CONF_DATA, UNIQUE_ID, create_entry, init_integration

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup_config_and_unload(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup and unload."""
    entry = await init_integration(hass, aioclient_mock)
    assert entry.state is ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.data == CONF_DATA

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_async_setup_entry_not_ready(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that it retries setup when the server can't be reached."""
    entry = create_entry(hass)
    aioclient_mock.get(
        "http://example.local:8090/command.cgi?cmd=getStatus",
        exc=aiohttp.ClientConnectionError,
    )
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_migrate_entry_from_version_1(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test migrating a pre-username/password config entry to version 2.

    Version 1 only had a `host` field; the only way to reach a Protect
    API secured server was to type credentials directly into it as
    `user:pass@host`, alongside a separately assembled `server_url`.
    """
    password = "p@ss/word&"
    legacy_host = f"matthias:{quote(password, safe='')}@example.local"
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        unique_id=UNIQUE_ID,
        data={
            CONF_HOST: legacy_host,
            CONF_PORT: 8090,
            SERVER_URL: f"http://{legacy_host}:8090/",
        },
    )
    entry.add_to_hass(hass)

    aioclient_mock.get(
        "http://example.local:8090/command.cgi?cmd=getStatus",
        text=(
            '{"unique": "'
            + UNIQUE_ID
            + '", "name": "DESKTOP", "version": "2.6.1.0", "armed": false}'
        ),
    )
    aioclient_mock.get(
        "http://example.local:8090/command.cgi?cmd=getObjects",
        text='{"locations": [], "objectList": []}',
    )
    aioclient_mock.get(
        "http://example.local:8090/command.cgi?cmd=getProfiles",
        text='{"profiles": []}',
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 2
    assert entry.data[CONF_HOST] == "example.local"
    assert entry.data[CONF_PORT] == 8090
    assert entry.data[CONF_USERNAME] == "matthias"
    assert entry.data[CONF_PASSWORD] == password
    assert entry.data[CONF_SSL] is False
