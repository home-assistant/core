"""The Bizkaibus bus tracker component."""

from bizkaibus.bizkaibusAPI import BizkaibusAPI, BizkaibusLanguages

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import CONF_STOP_ID
from .coordinator import BizkaibusConfigEntry, BizkaibusUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration."""
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
