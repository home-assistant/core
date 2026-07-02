"""The Picnic integration."""

from python_picnic_api2 import PicnicAPI

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_COUNTRY_CODE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import PicnicConfigEntry, PicnicUpdateCoordinator
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.SENSOR, Platform.TODO]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Picnic integration."""

    async_setup_services(hass)

    return True


def create_picnic_client(entry: PicnicConfigEntry):
    """Create an instance of the PicnicAPI client."""
    return PicnicAPI(
        auth_token=entry.data.get(CONF_ACCESS_TOKEN),
        country_code=entry.data.get(CONF_COUNTRY_CODE),
    )


async def async_setup_entry(hass: HomeAssistant, entry: PicnicConfigEntry) -> bool:
    """Set up Picnic from a config entry."""
    picnic_client = await hass.async_add_executor_job(create_picnic_client, entry)
    picnic_coordinator = PicnicUpdateCoordinator(hass, picnic_client, entry)

    # Fetch initial data so we have data when entities subscribe
    await picnic_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = picnic_coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PicnicConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
