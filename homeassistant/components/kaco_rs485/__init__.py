"""KACO RS485 integration."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CONF_ADDRESSES, CONF_INVERTERS, DOMAIN
from .coordinator import KacoRs485ConfigEntry, KacoRs485Coordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: KacoRs485ConfigEntry) -> None:
    """Set up KACO RS485 from a config entry."""
    _async_remove_stale_devices(hass, entry)

    coordinator = KacoRs485Coordinator(hass, entry, port=entry.data[CONF_PORT])

    # A failed setup must still release the port: two masters corrupt the bus.
    entry.async_on_unload(coordinator.async_close)

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: KacoRs485ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: KacoRs485ConfigEntry, device_entry: dr.AnyDeviceEntry
) -> bool:
    """Stop polling an inverter whose device the user deleted.

    Refused while it still answers. Once dark it may be removed or just asleep.
    """
    if (address := _address(entry, device_entry)) is None:
        return False
    if (
        entry.state is ConfigEntryState.LOADED
        and (state := entry.runtime_data.data.get(address)) is not None
        and state.available
    ):
        return False

    addresses = [a for a in entry.data[CONF_ADDRESSES] if a != address]
    inverters = dict(entry.data[CONF_INVERTERS])
    inverters.pop(str(address), None)
    hass.config_entries.async_update_entry(
        entry,
        data={**entry.data, CONF_ADDRESSES: addresses, CONF_INVERTERS: inverters},
    )
    # With no entities left the coordinator stops polling and keeps the port.
    if not addresses:
        hass.config_entries.async_schedule_reload(entry.entry_id)
    return True


def _address(entry: KacoRs485ConfigEntry, device: dr.AnyDeviceEntry) -> int | None:
    """Return the inverter address of one of this entry's devices."""
    prefix = f"{entry.entry_id}_"
    for domain, identifier in device.identifiers:
        if (
            domain == DOMAIN
            and identifier.startswith(prefix)
            and (address := identifier.removeprefix(prefix)).isdecimal()
        ):
            return int(address)
    return None


def _async_remove_stale_devices(
    hass: HomeAssistant, entry: KacoRs485ConfigEntry
) -> None:
    """Remove the devices of inverters the entry no longer lists."""
    registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        if (address := _address(entry, device)) is not None and (
            address not in entry.data[CONF_ADDRESSES]
        ):
            registry.async_remove_device(device.id)
