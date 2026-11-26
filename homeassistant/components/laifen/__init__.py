"""The Laifen integration."""

from laifen_ble import LaifenToothbrush

from homeassistant.const import CONF_ADDRESS, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import LaifenConfigEntry, LaifenCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: LaifenConfigEntry) -> None:
    """Set up Laifen from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, address)},
        connections={(dr.CONNECTION_BLUETOOTH, address)},
        manufacturer="Laifen",
        model="Wave",
        model_id="LFTB01-P",
        name=entry.title,
    )
    toothbrush = LaifenToothbrush(address)
    coordinator = LaifenCoordinator(hass, entry, toothbrush, device.id)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    async def _async_disconnect(event: Event) -> None:
        """Disconnect from the toothbrush when Home Assistant stops."""
        await toothbrush.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, _async_disconnect)
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: LaifenConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
