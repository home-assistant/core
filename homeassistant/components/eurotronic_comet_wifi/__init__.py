"""The Eurotronic Comet WiFi integration."""

from aiocometwifi import Thermostat

from homeassistant.components import mqtt
from homeassistant.const import CONF_MAC, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import CometWiFiConfigEntry, CometWiFiDataCoordinator
from .transport import get_mqtt_client

_PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: CometWiFiConfigEntry) -> bool:
    """Set up Eurotronic Comet WiFi from a config entry."""

    if not await mqtt.async_wait_for_mqtt_client(hass):
        raise ConfigEntryNotReady("MQTT integration not available.")

    client = Thermostat(get_mqtt_client(hass), entry.data[CONF_MAC])
    entry.async_on_unload(client.disconnect)  # No subscriptions are left behind

    coordinator = CometWiFiDataCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CometWiFiConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
