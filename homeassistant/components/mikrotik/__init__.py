"""The Mikrotik component."""

from typing import Any

from librouteros import Api

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import ATTR_MANUFACTURER, DOMAIN
from .coordinator import (
    MikrotikConfigEntry,
    MikrotikDataUpdateCoordinator,
    get_api,
    mikrotik_config_entry_errors,
)

PLATFORMS = [
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
]


def _call_api(data: dict[str, Any]) -> Api:
    """Call the Mikrotik API."""
    with mikrotik_config_entry_errors():
        api: Api = get_api(data)
        return api


async def async_setup_entry(
    hass: HomeAssistant, config_entry: MikrotikConfigEntry
) -> bool:
    """Set up the Mikrotik component."""
    api = await hass.async_add_executor_job(_call_api, dict(config_entry.data))

    coordinator = MikrotikDataUpdateCoordinator(hass, config_entry, api)
    await hass.async_add_executor_job(coordinator.api.get_hub_details)
    await coordinator.async_config_entry_first_refresh()

    config_entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, coordinator.serial_num)},
        manufacturer=ATTR_MANUFACTURER,
        model=coordinator.model,
        name=coordinator.hostname,
        sw_version=coordinator.firmware,
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: MikrotikConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
