"""Tests for the Snapcast integration."""

from homeassistant.components.snapcast.const import CONF_CREATE_GROUP_ENTITIES
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the Snapcast integration in Home Assistant."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_CREATE_GROUP_ENTITIES: True}
    )

    await hass.async_block_till_done()
