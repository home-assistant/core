"""Tests for the Whirlpool Sixth Sense integration."""
from spencerassistant.components.whirlpool.const import DOMAIN
from spencerassistant.const import CONF_PASSWORD, CONF_USERNAME
from spencerassistant.core import spencerAssistant

from tests.common import MockConfigEntry


async def init_integration(hass: spencerAssistant) -> MockConfigEntry:
    """Set up the Whirlpool integration in spencer Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "nobody",
            CONF_PASSWORD: "qwerty",
        },
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
