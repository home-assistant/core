"""Initialize the dk_fuelprices component."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry

from .const import CONF_COMPANY, CONF_STATION, DOMAIN
from .coordinator import APIClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

type DkFuelpricesRuntimeData = dict[str, APIClient]
type DkFuelpricesConfigEntry = ConfigEntry[DkFuelpricesRuntimeData]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: DkFuelpricesConfigEntry
) -> bool:
    """Set up dk_fuelprices from a config entry."""
    config_entry.async_on_unload(config_entry.add_update_listener(_update_listener))
    api_key = config_entry.data.get(CONF_API_KEY)
    if not api_key:
        _LOGGER.error("Missing API key in config entry %s", config_entry.entry_id)
        return False

    runtime_data: DkFuelpricesRuntimeData = {}

    for subentry_id, subentry in config_entry.subentries.items():
        company = subentry.data.get(CONF_COMPANY)
        station = subentry.data.get(CONF_STATION)

        if not isinstance(company, str) or not isinstance(station, dict):
            _LOGGER.error("Invalid subentry data in %s", subentry_id)
            continue

        coordinator = APIClient(
            hass,
            api_key,
            company,
            station,
            {},
            subentry_id,
            config_entry,
        )
        runtime_data[subentry_id] = coordinator
        await coordinator.async_config_entry_first_refresh()

    config_entry.runtime_data = runtime_data
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def _update_listener(hass: HomeAssistant, entry: DkFuelpricesConfigEntry) -> None:
    """Handle options or subentry updates by reloading the entry."""
    hass.config_entries.async_schedule_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, config_entry: DkFuelpricesConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        config_entry.runtime_data = {}
    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: DkFuelpricesConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """Remove a config entry from a device."""

    return not any(
        identifier
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN and identifier[1] in config_entry.subentries
    )


def remove_stale_devices(
    hass: HomeAssistant,
    config_entry: DkFuelpricesConfigEntry,
    devices: dict[str, Any],
) -> None:
    """Remove stale devices from device registry."""
    device_registry = dr.async_get(hass)
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )
    all_device_ids = {device.deviceid for device in devices.values()}

    for device_entry in device_entries:
        device_id: str | None = None

        for identifier in device_entry.identifiers:
            if identifier[0] == DOMAIN:
                device_id = identifier[1]
                break

        if device_id is None or device_id not in all_device_ids:
            device_registry.async_update_device(
                device_entry.id, remove_config_entry_id=config_entry.entry_id
            )
