"""KACO RS485 integration."""

from homeassistant.const import CONF_PORT, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import CONF_ADDRESSES, DOMAIN
from .coordinator import KacoRs485ConfigEntry, KacoRs485Coordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


def _enabled_addresses(hass: HomeAssistant, entry: KacoRs485ConfigEntry) -> list[int]:
    """Return the addresses whose device has not been disabled.

    One inverter costs a request pair and the pacing gaps around it, so a
    disabled one is dropped from the cycle rather than merely hidden: on a
    shared wire that time is what the others need.
    """
    registry = dr.async_get(hass)
    return [
        address
        for address in entry.data[CONF_ADDRESSES]
        if (
            device := registry.async_get_device_by_identifier(
                (DOMAIN, f"{entry.entry_id}_{address}"), entry.entry_id
            )
        )
        is None
        or not device.disabled
    ]


async def async_setup_entry(hass: HomeAssistant, entry: KacoRs485ConfigEntry) -> bool:
    """Set up KACO RS485 from a config entry."""
    coordinator = KacoRs485Coordinator(
        hass,
        entry,
        port=entry.data[CONF_PORT],
        addresses=_enabled_addresses(hass, entry),
    )

    # A failed setup must still release the port: two masters corrupt the bus.
    entry.async_on_unload(coordinator.async_close)

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    @callback
    def _reload_on_disable(event: Event[dr.EventDeviceRegistryUpdatedData]) -> None:
        """Rebuild the poll cycle when an inverter is enabled or disabled."""
        if (
            event.data["action"] != "update"
            or "disabled_by" not in event.data["changes"]
        ):
            return
        device = dr.async_get(hass).async_get(event.data["device_id"])
        if device is not None and entry.entry_id in device.config_entries:
            hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(
        hass.bus.async_listen(dr.EVENT_DEVICE_REGISTRY_UPDATED, _reload_on_disable)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: KacoRs485ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
