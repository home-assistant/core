"""The rtl_433 integration.

A single **hub** config entry owns one rtl_433 server's WebSocket connection.
Setting one up builds the push :class:`Rtl433Coordinator`, registers the hub
device, and forwards the ``sensor`` platform. RF devices are represented as
device-registry devices nested under the hub entry.
"""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, MANUFACTURER, PLATFORMS
from .coordinator import Rtl433ConfigEntry, Rtl433Coordinator


async def async_setup_entry(hass: HomeAssistant, entry: Rtl433ConfigEntry) -> bool:
    """Set up an rtl_433 hub config entry."""
    coordinator = Rtl433Coordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Register the hub device so nested RF devices can link to it via
    # ``via_device``. Identifier per COMPATIBILITY_CONTRACT.md section 3.
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


async def async_unload_entry(hass: HomeAssistant, entry: Rtl433ConfigEntry) -> bool:
    """Unload the hub config entry and its forwarded platforms."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
