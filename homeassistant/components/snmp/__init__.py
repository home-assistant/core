"""The SNMP integration."""

from dataclasses import dataclass
import logging

from pysnmp.error import PySnmpError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .client import SnmpClient
from .const import DOMAIN, SUBENTRY_TYPE_DEVICE_TRACKER
from .coordinator import SnmpDeviceTrackerCoordinator
from .util import async_get_snmp_engine

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER]

__all__ = ["async_get_snmp_engine"]


@dataclass
class SnmpRuntimeData:
    """Runtime data of an SNMP config entry."""

    client: SnmpClient
    coordinators: dict[str, SnmpDeviceTrackerCoordinator]


type SnmpConfigEntry = ConfigEntry[SnmpRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: SnmpConfigEntry) -> bool:
    """Set up SNMP from a config entry."""
    try:
        client = await SnmpClient.async_create(hass, entry.data)
    except PySnmpError as err:
        raise ConfigEntryNotReady(f"Unable to set up the SNMP device: {err}") from err

    # The name of the device is read once, it is not polled
    sys_name = await client.async_get_sys_name()

    coordinators = {
        subentry.subentry_id: SnmpDeviceTrackerCoordinator(
            hass, entry, subentry, client
        )
        for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_DEVICE_TRACKER)
    }
    for coordinator in coordinators.values():
        await coordinator.async_config_entry_first_refresh()

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=sys_name or entry.title,
    )

    entry.runtime_data = SnmpRuntimeData(client=client, coordinators=coordinators)

    if coordinators:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: SnmpConfigEntry) -> None:
    """Reload the entry when its subentries change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SnmpConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
