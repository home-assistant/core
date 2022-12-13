"""The Honeygain integration."""
from __future__ import annotations

from datetime import timedelta

from pyHoneygain import HoneyGain

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.util import Throttle

from .const import DOMAIN, LOGGER, UPDATE_INTERVAL_MINS

PLATFORMS: list[Platform] = [Platform.SENSOR]

UPDATE_INTERVAL = timedelta(minutes=UPDATE_INTERVAL_MINS)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Honeygain from a config entry."""
    hg_account = await validate_authentication(hass, entry)
    await hass.async_add_executor_job(hg_account.update)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = hg_account

    # Set up all platforms for this device/entry.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def validate_authentication(
    hass: HomeAssistant, entry: ConfigEntry
) -> HoneygainData:
    """Create and authenticate an API instance."""
    honeygain = HoneyGain()
    await hass.async_add_executor_job(
        honeygain.login, entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD]
    )
    hg_account = HoneygainData(honeygain)
    return hg_account


class HoneygainData:
    """Poll for new data."""

    def __init__(self, honeygain: HoneyGain) -> None:
        """Create instance ready for data updates."""
        self.honeygain: HoneyGain = honeygain
        self.user: dict = {}
        self.balances: dict = {}
        self.stats: dict = {}

    @Throttle(UPDATE_INTERVAL)
    def update(self) -> None:
        """Pull the latest data."""
        try:
            self.user = self.honeygain.me()
            self.balances = self.honeygain.balances()
            self.stats = self.honeygain.stats()
        except ConnectionError:
            LOGGER.warning("Failed to connect to Honeygain for update")
