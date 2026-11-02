"""The SNMP integration."""

from pysnmp.error import PySnmpError

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .client import SnmpClient
from .const import SUBENTRY_TYPE_DEVICE_TRACKER
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

    if coordinators:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: SnmpConfigEntry) -> None:
    """Reload the entry when its subentries change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SnmpConfigEntry) -> None:
    """Unload a config entry."""
    if not entry.runtime_data.coordinators:
        return
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
