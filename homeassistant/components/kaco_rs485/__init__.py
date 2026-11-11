"""KACO RS485 integration."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CONF_ADDRESSES, CONF_INVERTERS
from .coordinator import KacoRs485ConfigEntry, KacoRs485Coordinator, device_identifier

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
    """Allow deleting an inverter once it stops answering, and stop polling it.

    At night a removed inverter looks the same as a sleeping one.
    """
    address = next(
        (
            a
            for a in entry.data[CONF_ADDRESSES]
            if device_identifier(entry, a) in device_entry.identifiers
        ),
        None,
    )
    if address is None:
        return True
    if (
        entry.state is ConfigEntryState.LOADED
        and entry.runtime_data.last_update_success
        and (state := entry.runtime_data.data.get(address))
        and state.available
    ):
        return False

    addresses = [a for a in entry.data[CONF_ADDRESSES] if a != address]
    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            CONF_ADDRESSES: addresses,
            CONF_INVERTERS: {
                key: inverter
                for key, inverter in entry.data[CONF_INVERTERS].items()
                if key != str(address)
            },
        },
    )
    return True


def _async_remove_stale_devices(
    hass: HomeAssistant, entry: KacoRs485ConfigEntry
) -> None:
    """Remove the devices of inverters the entry no longer lists."""
    configured = {device_identifier(entry, a) for a in entry.data[CONF_ADDRESSES]}
    registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        if device.identifiers.isdisjoint(configured):
            registry.async_remove_device(device.id)
