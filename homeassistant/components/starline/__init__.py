"""The StarLine component."""
import homeassistant.util.dt as dt_util

from homeassistant.core import Config, HomeAssistant
from homeassistant.helpers.event import async_track_utc_time_change

from .api import StarlineApi
from .config_flow import StarlineFlowHandler
from .const import DOMAIN, UPDATE_INTERVAL, PLATFORMS


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up configured StarLine."""
    return True


async def async_setup_entry(hass, config_entry):
    api = StarlineApi(config_entry.data["user_id"], config_entry.data["slnet_token"])
    api.update()
    hass.data[DOMAIN] = api

    device_registry = await hass.helpers.device_registry.async_get_registry()
    for device_id, device in api.devices.items():
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            **device.device_info
        )

    for domain in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, domain)
        )

    now = dt_util.utcnow()
    async_track_utc_time_change(
        hass,
        api.update,
        minute=range(now.minute % UPDATE_INTERVAL, 60, UPDATE_INTERVAL),
        second=now.second,
    )
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    for domain in PLATFORMS:
        await hass.config_entries.async_forward_entry_unload(config_entry, domain)
    return True
