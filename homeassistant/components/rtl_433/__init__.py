"""The rtl_433 integration.

A single hub config entry owns one rtl_433 server's WebSocket connection.
Setting one up builds the push :class:`Rtl433Coordinator`, registers the hub
device, and forwards the ``sensor`` platform. RF devices are represented as
device-registry devices nested under the hub entry.
"""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, LOGGER, MANUFACTURER, PLATFORMS
from .coordinator import Rtl433ConfigEntry, Rtl433Coordinator


async def async_setup_entry(hass: HomeAssistant, entry: Rtl433ConfigEntry) -> bool:
    """Set up an rtl_433 hub config entry."""
    coordinator = Rtl433Coordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Registered here so RF devices can point at the hub via ``via_device``.
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer=MANUFACTURER,
        name=entry.title,
        model="rtl_433 server",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate a hub config entry.

    Every schema this integration reads is a version 2 one, so all minor versions
    load as-is. Version 1 entries predate the hub entry owning its devices and are
    only produced by the custom component of the same domain, which owns that
    migration; upgrading it first is what moves such an entry to version 2.
    """
    if entry.version == 1:
        LOGGER.error(
            "Config entry %s is at schema version 1, which this integration cannot"
            " migrate. Upgrade the rtl_433 custom component first, then remove it",
            entry.title,
        )
        return False

    return True


async def async_unload_entry(hass: HomeAssistant, entry: Rtl433ConfigEntry) -> bool:
    """Unload the hub config entry and its forwarded platforms."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
