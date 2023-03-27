"""The Synology DSM component."""
from __future__ import annotations

from itertools import chain
import logging

from synology_dsm.api.surveillance_station import SynoSurveillanceStation
from synology_dsm.api.surveillance_station.camera import SynoCamera

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .common import SynoApi
from .const import (
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    EXCEPTION_DETAILS,
    EXCEPTION_UNKNOWN,
    PLATFORMS,
    SYNOLOGY_AUTH_FAILED_EXCEPTIONS,
    SYNOLOGY_CONNECTION_EXCEPTIONS,
)
from .coordinator import (
    SynologyDSMCameraUpdateCoordinator,
    SynologyDSMCentralUpdateCoordinator,
    SynologyDSMSwitchUpdateCoordinator,
)
from .models import SynologyDSMData
from .service import async_setup_services

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Synology DSM sensors."""

    # Migrate device indentifiers
    dev_reg = dr.async_get(hass)
    devices: list[dr.DeviceEntry] = dr.async_entries_for_config_entry(
        dev_reg, entry.entry_id
    )
    for device in devices:
        old_identifier = list(next(iter(device.identifiers)))
        if len(old_identifier) > 2:
            new_identifier = {
                (old_identifier.pop(0), "_".join([str(x) for x in old_identifier]))
            }
            _LOGGER.debug(
                "migrate identifier '%s' to '%s'", device.identifiers, new_identifier
            )
            dev_reg.async_update_device(device.id, new_identifiers=new_identifier)

    # Migrate existing entry configuration
    if entry.data.get(CONF_VERIFY_SSL) is None:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL}
        )

    # Continue setup
    api = SynoApi(hass, entry)
    try:
        await api.async_setup()
    except SYNOLOGY_AUTH_FAILED_EXCEPTIONS as err:
        if err.args[0] and isinstance(err.args[0], dict):
            details = err.args[0].get(EXCEPTION_DETAILS, EXCEPTION_UNKNOWN)
        else:
            details = EXCEPTION_UNKNOWN
        raise ConfigEntryAuthFailed(f"reason: {details}") from err
    except SYNOLOGY_CONNECTION_EXCEPTIONS as err:
        if err.args[0] and isinstance(err.args[0], dict):
            details = err.args[0].get(EXCEPTION_DETAILS, EXCEPTION_UNKNOWN)
        else:
            details = EXCEPTION_UNKNOWN
        raise ConfigEntryNotReady(details) from err

    # Services
    await async_setup_services(hass)

    # For SSDP compat
    if not entry.data.get(CONF_MAC):
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_MAC: api.dsm.network.macs}
        )

    coordinator_central = SynologyDSMCentralUpdateCoordinator(hass, entry, api)
    await coordinator_central.async_config_entry_first_refresh()

    available_apis = api.dsm.apis

    # The central coordinator needs to be refreshed first since
    # the next two rely on data from it
    coordinator_cameras: SynologyDSMCameraUpdateCoordinator | None = None
    if api.surveillance_station is not None:
        coordinator_cameras = SynologyDSMCameraUpdateCoordinator(hass, entry, api)
        await coordinator_cameras.async_config_entry_first_refresh()

    coordinator_switches: SynologyDSMSwitchUpdateCoordinator | None = None
    if (
        SynoSurveillanceStation.INFO_API_KEY in available_apis
        and SynoSurveillanceStation.HOME_MODE_API_KEY in available_apis
    ):
        coordinator_switches = SynologyDSMSwitchUpdateCoordinator(hass, entry, api)
        await coordinator_switches.async_config_entry_first_refresh()
        try:
            await coordinator_switches.async_setup()
        except SYNOLOGY_CONNECTION_EXCEPTIONS as ex:
            raise ConfigEntryNotReady from ex

    synology_data = SynologyDSMData(
        api=api,
        coordinator_central=coordinator_central,
        coordinator_cameras=coordinator_cameras,
        coordinator_switches=coordinator_switches,
    )
    hass.data.setdefault(DOMAIN, {})[entry.unique_id] = synology_data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Synology DSM sensors."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        entry_data: SynologyDSMData = hass.data[DOMAIN][entry.unique_id]
        await entry_data.api.async_unload()
        hass.data[DOMAIN].pop(entry.unique_id)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove synology_dsm config entry from a device."""
    data: SynologyDSMData = hass.data[DOMAIN][entry.unique_id]
    api = data.api
    serial = api.information.serial
    storage = api.storage
    # get_all_cameras does not do I/O
    all_cameras: list[SynoCamera] = api.surveillance_station.get_all_cameras()
    device_ids = chain(
        (camera.id for camera in all_cameras),
        storage.volumes_ids,
        storage.disks_ids,
        storage.volumes_ids,
        (SynoSurveillanceStation.INFO_API_KEY,),  # Camera home/away
    )
    return not device_entry.identifiers.intersection(
        (
            (DOMAIN, serial),  # Base device
            *((DOMAIN, f"{serial}_{id}") for id in device_ids),  # Storage and cameras
        )
    )
