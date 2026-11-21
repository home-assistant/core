"""The SNMP integration."""

from pysnmp.error import PySnmpError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .client import SnmpClient
from .const import DOMAIN, SUBENTRY_TYPE_DEVICE_TRACKER
from .coordinator import SnmpConfigEntry, SnmpDeviceTrackerCoordinator, SnmpRuntimeData
from .util import async_get_snmp_engine

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER]

__all__ = ["async_get_snmp_engine"]


async def async_setup_entry(hass: HomeAssistant, entry: SnmpConfigEntry) -> None:
    """Set up SNMP from a config entry."""
    # Registered before the first await: a subentry added while the device is
    # polled has to schedule a reload, or it is silently dropped.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    try:
        client = await SnmpClient.async_create(hass, entry.data)
    except PySnmpError as err:
        raise ConfigEntryNotReady(f"Unable to set up the SNMP device: {err}") from err

    coordinators = {
        subentry.subentry_id: SnmpDeviceTrackerCoordinator(
            hass, entry, subentry, client
        )
        for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_DEVICE_TRACKER)
    }
    for coordinator in coordinators.values():
        await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = SnmpRuntimeData(client=client, coordinators=coordinators)

    # The tracker devices link to the SNMP device through via_device_id, which can
    # only resolve a device which already exists. The name follows the entry, so a
    # reconfigure which renames the host renames the device too.
    dr.async_get(hass).async_get_or_create_from_info(
        config_entry_id=entry.entry_id,
        device_info=DeviceInfo(
            name=entry.title, identifiers={(DOMAIN, entry.entry_id)}
        ),
    )

    if not coordinators:
        return

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: SnmpConfigEntry) -> None:
    """Reload the entry when its title, credentials or subentries change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SnmpConfigEntry) -> None:
    """Unload a config entry."""
    if not entry.runtime_data.coordinators:
        return
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: SnmpConfigEntry,
    device_entry: dr.AnyDeviceEntry,
) -> bool:
    """Allow removing a tracker whose MAC the watched table does not report."""
    if not isinstance(device_entry, dr.DeviceEntry):
        return False
    if (DOMAIN, config_entry.entry_id) in device_entry.identifiers:
        # The SNMP device is the entry itself, not one of its trackers
        return False
    macs = {
        mac
        for connection_type, mac in device_entry.connections
        if connection_type == dr.CONNECTION_NETWORK_MAC
    }
    if not macs:
        return False
    if config_entry.state is not ConfigEntryState.LOADED:
        # Nothing polls the table, so a tracker cannot reappear on its own
        return True
    tracked_macs = {
        mac
        for coordinator in config_entry.runtime_data.coordinators.values()
        for mac in coordinator.data or {}
    }
    return not macs & tracked_macs
