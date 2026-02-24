"""Initialize the dk_fuelprices component."""

from __future__ import annotations

import logging
from types import MappingProxyType
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState, ConfigSubentry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry

from .const import CONF_COMPANY, CONF_PRODUCTS, CONF_STATION, DOMAIN
from .coordinator import APIClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

type DkFuelpricesRuntimeData = dict[str, APIClient]
type DkFuelpricesConfigEntry = ConfigEntry[DkFuelpricesRuntimeData]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: DkFuelpricesConfigEntry
) -> bool:
    """Set up dk_fuelprices from a config entry."""
    config_entry.async_on_unload(config_entry.add_update_listener(_update_listener))
    runtime_data = await _setup(hass, config_entry)
    if runtime_data is None:
        return False
    config_entry.runtime_data = runtime_data

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def _update_listener(hass: HomeAssistant, entry: DkFuelpricesConfigEntry) -> None:
    """Handle options or subentry updates by reloading the entry."""
    hass.config_entries.async_schedule_reload(entry.entry_id)


async def _setup(
    hass: HomeAssistant, config_entry: DkFuelpricesConfigEntry
) -> DkFuelpricesRuntimeData | None:
    """Set up the integration."""
    runtime_data: DkFuelpricesRuntimeData = {}

    config_entry = await _ensure_initial_subentry(hass, config_entry)
    api_key = config_entry.data.get(CONF_API_KEY)
    if not api_key:
        _LOGGER.error("Missing API key in config entry %s", config_entry.entry_id)
        return None

    for subentry_id, subentry in config_entry.subentries.items():
        company = subentry.data.get(CONF_COMPANY)
        station = subentry.data.get(CONF_STATION)
        products = subentry.data.get(CONF_PRODUCTS, {})

        if not isinstance(company, str) or not isinstance(station, dict):
            _LOGGER.error("Invalid subentry data in %s", subentry_id)
            continue
        if not isinstance(products, dict):
            products = {}

        coordinator = APIClient(
            hass,
            api_key,
            company,
            station,
            products,
            subentry_id,
            config_entry,
        )
        runtime_data[subentry_id] = coordinator

        if config_entry.state == ConfigEntryState.SETUP_IN_PROGRESS:
            await coordinator.async_config_entry_first_refresh()

    return runtime_data


async def _ensure_initial_subentry(
    hass: HomeAssistant, config_entry: DkFuelpricesConfigEntry
) -> DkFuelpricesConfigEntry:
    """Create the first subentry from initial config flow data if missing."""
    if config_entry.subentries:
        return config_entry

    company = config_entry.data.get(CONF_COMPANY)
    station = config_entry.data.get(CONF_STATION)
    products = config_entry.data.get(CONF_PRODUCTS)
    if not (company and station and products):
        return config_entry

    subentry_data = {
        CONF_COMPANY: company,
        CONF_STATION: station,
        CONF_PRODUCTS: products,
    }
    subentry_title = f"{company} - {station['name']}" if station else f"{company}"
    unique_id = f"{company}_{station['id']}" if station else None

    subentry = ConfigSubentry(
        data=MappingProxyType(subentry_data),
        subentry_type="station",
        title=subentry_title,
        unique_id=unique_id,
    )

    hass.config_entries.async_update_entry(
        config_entry,
        data={CONF_API_KEY: config_entry.data.get(CONF_API_KEY)},
    )
    hass.config_entries.async_add_subentry(config_entry, subentry)

    return hass.config_entries.async_get_entry(config_entry.entry_id) or config_entry


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
