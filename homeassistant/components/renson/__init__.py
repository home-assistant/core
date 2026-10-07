"""The Renson integration."""

from renson_endura_delta.renson import RensonVentilation

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import RensonConfigEntry, RensonCoordinator, RensonData
from .services import async_setup_services

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.FAN,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Renson integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: RensonConfigEntry) -> bool:
    """Set up Renson from a config entry."""

    api = RensonVentilation(entry.data[CONF_HOST])
    coordinator = RensonCoordinator(hass, entry, api)

    if not await hass.async_add_executor_job(api.connect):
        raise ConfigEntryNotReady("Cannot connect to Renson device")

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = RensonData(
        api,
        coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: RensonConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
