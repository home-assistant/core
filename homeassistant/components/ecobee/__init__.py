"""Support for ecobee."""

from datetime import timedelta

from pyecobee import ECOBEE_API_KEY, ECOBEE_REFRESH_TOKEN, Ecobee, ExpiredTokenError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.util import Throttle

from .const import _LOGGER, CONF_REFRESH_TOKEN, PLATFORMS

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=180)

type EcobeeConfigEntry = ConfigEntry[EcobeeData]


async def async_setup_entry(hass: HomeAssistant, entry: EcobeeConfigEntry) -> bool:
    """Set up ecobee via a config entry."""
    api_key = entry.data[CONF_API_KEY]
    refresh_token = entry.data[CONF_REFRESH_TOKEN]

    runtime_data = EcobeeData(hass, entry, api_key=api_key, refresh_token=refresh_token)

    if not await runtime_data.refresh():
        return False

    await runtime_data.update()

    if runtime_data.ecobee.thermostats is None:
        _LOGGER.error("No ecobee devices found to set up")
        return False

    entry.runtime_data = runtime_data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


class EcobeeData:
    """Handle getting the latest data from ecobee.com so platforms can use it.

    Also handle refreshing tokens and updating config entry with refreshed tokens.
    """

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, api_key: str, refresh_token: str
    ) -> None:
        """Initialize the Ecobee data object."""
        self._hass = hass
        self.entry = entry
        self.ecobee = Ecobee(
            config={ECOBEE_API_KEY: api_key, ECOBEE_REFRESH_TOKEN: refresh_token}
        )

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def update(self):
        """Get the latest data from ecobee.com."""
        try:
            await self._hass.async_add_executor_job(self.ecobee.update)
            _LOGGER.debug("Updating ecobee")
        except ExpiredTokenError:
            _LOGGER.debug("Refreshing expired ecobee tokens")
            await self.refresh()

    async def refresh(self) -> bool:
        """Refresh ecobee tokens and update config entry."""
        _LOGGER.debug("Refreshing ecobee tokens and updating config entry")
        if await self._hass.async_add_executor_job(self.ecobee.refresh_tokens):
            self._hass.config_entries.async_update_entry(
                self.entry,
                data={
                    CONF_API_KEY: self.ecobee.config[ECOBEE_API_KEY],
                    CONF_REFRESH_TOKEN: self.ecobee.config[ECOBEE_REFRESH_TOKEN],
                },
            )
            return True
        _LOGGER.error("Error refreshing ecobee tokens")
        return False


async def async_unload_entry(hass: HomeAssistant, entry: EcobeeConfigEntry) -> bool:
    """Unload the config entry and platforms."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
