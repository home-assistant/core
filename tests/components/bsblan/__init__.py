"""Tests for the bsblan integration."""

from homeassistant.components.bsblan.const import (
    CONF_DEVICE_IDENT,
    CONF_PASSKEY,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


async def init_integration(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, skip_setup: bool = False,
) -> MockConfigEntry:
    """Set up the BSBLan integration in Home Assistant."""

    aioclient_mock.post(
        "http://example.local:80/1234/JQ?Parameter=6224,6225,6226",
        params={"Parameter": "6224,6225,6226"},
        text=load_fixture("bsblan/info.json"),
        headers={"Content-Type": "application/json"},
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="RVS21.831F/127",
        data={
            CONF_HOST: "example.local",
            CONF_PASSKEY: "1234",
            CONF_PORT: 80,
            CONF_DEVICE_IDENT: "RVS21.831F/127",
        },
    )

    entry.add_to_hass(hass)

    if not skip_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
