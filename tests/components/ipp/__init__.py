"""Tests for the IPP integration."""
import os

from homeassistant.components.ipp.const import CONF_BASE_PATH, CONF_UUID, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


def load_fixture_binary(filename):
    """Load a binary fixture."""
    path = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", filename)
    with open(path, "rb") as fptr:
        return fptr.read()


async def init_integration(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, skip_setup: bool = False,
) -> MockConfigEntry:
    """Set up the IPP integration in Home Assistant."""

    fixture = "ipp/get-printer-attributes.bin"
    aioclient_mock.post(
        "http://EPSON123456.local:631/ipp/print",
        content=load_fixture_binary(fixture),
        headers={"Content-Type": "application/ipp"},
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "EPSON123456.local",
            CONF_PORT: 631,
            CONF_SSL: False,
            CONF_VERIFY_SSL: True,
            CONF_BASE_PATH: "/ipp/print",
            CONF_UUID: "cfe92100-67c4-11d4-a45f-f8d027761251",
        },
    )

    entry.add_to_hass(hass)

    if not skip_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
