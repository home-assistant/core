"""Tests for the agent_dvr component."""

from homeassistant.components.agent_dvr.const import DOMAIN, SERVER_URL
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


async def init_integration(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, skip_setup: bool = False,
) -> MockConfigEntry:
    """Set up the Agent DVR integration in Home Assistant."""

    aioclient_mock.get(
        "http://example.local:8090/command.cgi?cmd=getStatus",
        text=load_fixture("agent_dvr/status.json"),
        headers={"Content-Type": "application/json"},
    )
    aioclient_mock.get(
        "http://example.local:8090/command.cgi?cmd=getObjects",
        text=load_fixture("agent_dvr/objects.json"),
        headers={"Content-Type": "application/json"},
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="c0715bba-c2d0-48ef-9e3e-bc81c9ea4447",
        data={
            CONF_HOST: "example.local",
            CONF_PORT: 8090,
            SERVER_URL: "http://example.local:8090/",
        },
    )

    entry.add_to_hass(hass)

    if not skip_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
