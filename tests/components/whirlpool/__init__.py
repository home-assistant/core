"""Tests for the Whirlpool Sixth Sense integration."""

from homeassistant.components.whirlpool.const import CONF_BRAND, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def init_integration(
    hass: HomeAssistant, region: str = "EU", brand: str = "Whirlpool"
) -> MockConfigEntry:
    """Set up the Whirlpool integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "nobody",
            CONF_PASSWORD: "qwerty",
            CONF_REGION: region,
            CONF_BRAND: brand,
        },
    )

    return await init_integration_with_entry(hass, entry)


async def init_integration_with_entry(
    hass: HomeAssistant, entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the Whirlpool integration in Home Assistant."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
