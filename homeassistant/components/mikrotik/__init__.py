"""The Mikrotik component."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import ATTR_MANUFACTURER, DOMAIN
from .coordinator import MikrotikDataUpdateCoordinator, get_api
from .errors import CannotConnect, LoginError

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)

PLATFORMS = [Platform.DEVICE_TRACKER]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Mikrotik component."""
    try:
        api = await hass.async_add_executor_job(get_api, dict(config_entry.data))
    except CannotConnect as api_error:
        raise ConfigEntryNotReady from api_error
    except LoginError as err:
        raise ConfigEntryAuthFailed from err

    coordinator = MikrotikDataUpdateCoordinator(hass, config_entry, api)
    await hass.async_add_executor_job(coordinator.api.get_hub_details)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(DOMAIN, coordinator.serial_num)},
        manufacturer=ATTR_MANUFACTURER,
        model=coordinator.model,
        name=coordinator.hostname,
        sw_version=coordinator.firmware,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    ):
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
