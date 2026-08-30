"""The AfterShip integration."""

from pyaftership import AfterShip, AfterShipException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS: list[Platform] = [Platform.SENSOR]

type AfterShipConfigEntry = ConfigEntry[AfterShip]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up AfterShip."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AfterShipConfigEntry) -> bool:
    """Set up AfterShip from a config entry."""

    session = async_get_clientsession(hass)
    aftership = AfterShip(api_key=entry.data[CONF_API_KEY], session=session)

    try:
        await aftership.trackings.list()
    except AfterShipException as err:
        raise ConfigEntryNotReady from err

    entry.runtime_data = aftership

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
