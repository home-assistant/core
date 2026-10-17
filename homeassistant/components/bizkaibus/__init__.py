"""The Bizkaibus bus tracker component."""

from bizkaibus import (
    BizkaibusAPI,
    BizkaibusConnectionError,
    BizkaibusLanguages,
    BizkaibusParseError,
    BizkaibusStopNotFoundError,
)
import probatio

from homeassistant.components.sensor import PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import CONF_LINES, CONF_STOP_ID
from .coordinator import BizkaibusConfigEntry, BizkaibusUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]
PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_STOP_ID): cv.string,
        probatio.Optional(CONF_LINES): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: BizkaibusConfigEntry) -> bool:
    """Config entry example."""

    try:
        my_api = await BizkaibusAPI.create(
            BizkaibusLanguages.ES,
            entry.data[CONF_STOP_ID],
            session=async_get_clientsession(hass),
        )
    except BizkaibusStopNotFoundError as err:
        raise ConfigEntryError("The requested stop does not exist") from err
    except BizkaibusConnectionError as err:
        raise ConfigEntryNotReady("Could not contact the Bizkaibus service") from err
    except BizkaibusParseError as err:
        raise ConfigEntryNotReady(
            "The Bizkaibus service returned an invalid response"
        ) from err

    coordinator = BizkaibusUpdateCoordinator(hass, my_api, entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BizkaibusConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
