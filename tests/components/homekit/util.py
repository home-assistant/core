"""Test util for the homekit integration."""

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.homekit.const import DOMAIN, TARGET_CHANGE_RELOAD_COOLDOWN
from homeassistant.const import CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed

PATH_HOMEKIT = "homeassistant.components.homekit"


async def async_fire_target_change_cooldown(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Fire the target change reload cooldown timer."""
    freezer.tick(TARGET_CHANGE_RELOAD_COOLDOWN)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def async_init_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the homekit integration in Home Assistant."""

    with patch(f"{PATH_HOMEKIT}.HomeKit.async_start"):
        entry = MockConfigEntry(
            domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry


async def async_init_entry(hass: HomeAssistant, entry: MockConfigEntry):
    """Set up the homekit integration in Home Assistant."""

    with patch(f"{PATH_HOMEKIT}.HomeKit.async_start"):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry
