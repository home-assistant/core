"""The Mikrotik component."""

from typing import Any

from librouteros import Api

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.util import slugify

from .const import ATTR_MANUFACTURER, DOMAIN
from .coordinator import (
    MikrotikConfigEntry,
    MikrotikDataUpdateCoordinator,
    get_api,
    mikrotik_config_entry_errors,
)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]


def _call_api(data: dict[str, Any]) -> Api:
    """Call the Mikrotik API."""
    with mikrotik_config_entry_errors(during_setup=True):
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

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, coordinator.serial_num)},
        manufacturer=ATTR_MANUFACTURER,
        model=coordinator.model,
        name=coordinator.hostname,
        sw_version=coordinator.firmware,
    )

    @callback
    def _async_remove_stale_devices() -> None:
        """Remove interface devices the hub no longer reports."""
        known_identifiers = {(DOMAIN, coordinator.serial_num)}
        for interface in coordinator.api.interfaces:
            if (mac := interface.get("mac-address")) and (
                name := interface.get("name")
            ):
                known_identifiers.add((DOMAIN, f"{slugify(mac)}_{name}"))

        for device_entry in dr.async_entries_for_config_entry(
            device_registry, config_entry.entry_id
        ):
            own_identifiers = {
                identifier
                for identifier in device_entry.identifiers
                if identifier[0] == DOMAIN
            }
            # device-tracker clients are linked by MAC connection only, so an
            # entry without an own identifier is never an interface device
            if own_identifiers and own_identifiers.isdisjoint(known_identifiers):
                device_registry.async_remove_device(device_entry.id)

    _async_remove_stale_devices()
    config_entry.async_on_unload(
        coordinator.async_add_listener(_async_remove_stale_devices)
    )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: MikrotikConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        await hass.async_add_executor_job(config_entry.runtime_data.api.api.close)
    return unload_ok
