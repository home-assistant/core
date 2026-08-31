"""Tests for the Silla Prism integration."""

from homeassistant.core import HomeAssistant

from .const import RETAINED_BURST

from tests.common import MockConfigEntry, async_fire_mqtt_message


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the Silla Prism integration."""
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def fire_burst(hass: HomeAssistant) -> None:
    """Publish the retained status burst captured from a real Prism."""
    for topic, payload in RETAINED_BURST:
        async_fire_mqtt_message(hass, topic, payload)
    await hass.async_block_till_done()
