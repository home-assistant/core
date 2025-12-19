"""The Bizkaibus bus tracker component."""

from bizkaibus.bizkaibusAPI import BizkaibusAPI, BizkaibusLanguages
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import CONF_STOP_ID, LINE_ID
from .coordinator import BizkaibusConfigEntry, BizkaibusUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]
PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_STOP_ID): cv.string,
        vol.Optional(LINE_ID): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, entry: BizkaibusConfigEntry) -> bool:
    """Set up entry."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: BizkaibusConfigEntry) -> bool:
    """Config entry example."""

    my_api = BizkaibusAPI(BizkaibusLanguages.ES, entry.data[CONF_STOP_ID])
    coordinator = BizkaibusUpdateCoordinator(hass, my_api, entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BizkaibusConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
