"""Tests for the agent_dvr component."""

from homeassistant.components.agent_dvr.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, CONTENT_TYPE_JSON
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

UNIQUE_ID = "c0715bba-c2d0-48ef-9e3e-bc81c9ea4447"

CONF_DATA = {
    CONF_HOST: "example.local",
    CONF_PORT: 8090,
    CONF_SSL: False,
}


def create_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add config entry in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id=UNIQUE_ID,
        data=CONF_DATA,
    )
    entry.add_to_hass(hass)
    return entry


def mock_agent_dvr_requests(aioclient_mock: AiohttpClientMocker, fixtures_hass) -> None:
    """Register the request/response pairs needed for a full setup."""
    aioclient_mock.get(
        "http://example.local:8090/command.cgi?cmd=getStatus",
        text=fixtures_hass["status"],
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )
    aioclient_mock.get(
        "http://example.local:8090/command.cgi?cmd=getObjects",
        text=fixtures_hass["objects"],
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )
    aioclient_mock.get(
        "http://example.local:8090/command.cgi?cmd=getProfiles",
        text=fixtures_hass["getprofiles"],
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )
    aioclient_mock.get(
        "http://example.local:8090/command.cgi?cmd=ptzpresets&oid=1&ot=2",
        text=fixtures_hass["ptzpresets"],
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )
    aioclient_mock.get(
        "http://example.local:8090/eventcounts.json",
        text='{"count": 3}',
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )


async def init_integration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    skip_setup: bool = False,
) -> MockConfigEntry:
    """Set up the Agent DVR integration in Home Assistant."""
    fixtures = {
        name: await async_load_fixture(hass, f"{name}.json", DOMAIN)
        for name in ("status", "objects", "getprofiles", "ptzpresets")
    }
    mock_agent_dvr_requests(aioclient_mock, fixtures)

    entry = create_entry(hass)

    if not skip_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
