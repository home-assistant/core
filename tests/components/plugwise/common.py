"""Common initialisation for the Plugwise integration."""

from homeassistant.components.plugwise.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def async_init_integration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    skip_setup: bool = False,
):
    """Initialize the Smile integration."""

    entry = MockConfigEntry(
        domain=DOMAIN, data={"host": "1.1.1.1", "password": "test-password"}
    )
    entry.add_to_hass(hass)

    if not skip_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
