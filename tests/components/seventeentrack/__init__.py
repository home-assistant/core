"""Tests for the seventeentrack component."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.seventeentrack.sensor import (
    CONF_SHOW_ARCHIVED,
    CONF_SHOW_DELIVERED,
    DEFAULT_SCAN_INTERVAL,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.seventeentrack.conftest import ACCOUNT_ID

VALID_PLATFORM_CONFIG_FULL = {
    "sensor": {
        "platform": "seventeentrack",
        CONF_USERNAME: "test",
        CONF_PASSWORD: "test",
        CONF_SHOW_ARCHIVED: True,
        CONF_SHOW_DELIVERED: True,
    }
}


NEW_SUMMARY_DATA = {
    "Not Found": 1,
    "In Transit": 1,
    "Expired": 1,
    "Ready to be Picked Up": 1,
    "Undelivered": 1,
    "Delivered": 1,
    "Returned": 1,
}

VALID_CONFIG = {
    CONF_USERNAME: "test",
    CONF_PASSWORD: "test",
}

INVALID_CONFIG = {"notusername": "seventeentrack", "notpassword": "test"}

VALID_OPTIONS = {
    CONF_SHOW_ARCHIVED: True,
    CONF_SHOW_DELIVERED: True,
}

NO_DELIVERED_OPTIONS = {
    CONF_SHOW_ARCHIVED: False,
    CONF_SHOW_DELIVERED: False,
}


async def _goto_future(hass: HomeAssistant, freezer: FrozenDateTimeFactory):
    """Move to future."""
    for _ in range(2):
        freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()


async def init_integration(
    hass: HomeAssistant, config, options=None
) -> MockConfigEntry:
    """Set up the 17Track integration in Home Assistant."""

    if options is None:
        options = {}
    entry = MockConfigEntry(
        domain="17Track",
        title="17Track",
        unique_id=ACCOUNT_ID,
        data=config,
        options=options,
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
