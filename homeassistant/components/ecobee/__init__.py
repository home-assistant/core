"""Support for ecobee."""
from datetime import timedelta

from pyecobee import ECOBEE_API_KEY, ECOBEE_REFRESH_TOKEN, Ecobee, ExpiredTokenError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import Throttle

from .const import _LOGGER, CONF_REFRESH_TOKEN, DATA_ECOBEE_CONFIG, DOMAIN, PLATFORMS

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=180)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Optional(CONF_API_KEY): cv.string})}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """
    Ecobee uses config flow for configuration.

    But, an "ecobee:" entry in configuration.yaml will trigger an import flow
    if a config entry doesn't already exist. If ecobee.conf exists, the import
    flow will attempt to import it and create a config entry, to assist users
    migrating from the old ecobee integration. Otherwise, the user will have to
    continue setting up the integration via the config flow.
    """
    hass.data[DATA_ECOBEE_CONFIG] = config.get(DOMAIN, {})

    if not hass.config_entries.async_entries(DOMAIN) and hass.data[DATA_ECOBEE_CONFIG]:
        # No config entry exists and configuration.yaml config exists, trigger the import flow.
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ecobee via a config entry."""
    api_key = entry.data[CONF_API_KEY]
    refresh_token = entry.data[CONF_REFRESH_TOKEN]

    data = EcobeeData(hass, entry, api_key=api_key, refresh_token=refresh_token)

    if not await data.refresh():
        return False

    await data.update()

    if data.ecobee.thermostats is None:
        _LOGGER.error("No ecobee devices found to set up")
        return False

    hass.data[DOMAIN] = data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


class EcobeeData:
    """
    Handle getting the latest data from ecobee.com so platforms can use it.

    Also handle refreshing tokens and updating config entry with refreshed tokens.
    """

    def __init__(self, hass, entry, api_key, refresh_token):
        """Initialize the Ecobee data object."""
        self._hass = hass
        self._entry = entry
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
                self._entry,
                data={
                    CONF_API_KEY: self.ecobee.config[ECOBEE_API_KEY],
                    CONF_REFRESH_TOKEN: self.ecobee.config[ECOBEE_REFRESH_TOKEN],
                },
            )
            return True
        _LOGGER.error("Error refreshing ecobee tokens")
        return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry and platforms."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.pop(DOMAIN)
    return unload_ok
