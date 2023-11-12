"""Get data from Smart Weather station via UDP."""
from __future__ import annotations

from pyweatherflowudp.client import EVENT_DEVICE_DISCOVERED, WeatherFlowListener
from pyweatherflowudp.device import EVENT_LOAD_COMPLETE, WeatherFlowDevice
from pyweatherflowudp.errors import ListenerError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.start import async_at_started

from .const import DOMAIN, LOGGER, format_dispatch_call

PLATFORMS = [
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WeatherFlow from a config entry."""

    client = WeatherFlowListener()

    @callback
    def _async_device_discovered(device: WeatherFlowDevice) -> None:
        LOGGER.debug("Found a device: %s", device)

        @callback
        def _async_add_device_if_started(device: WeatherFlowDevice):
            async_at_started(
                hass,
                callback(
                    lambda _: async_dispatcher_send(
                        hass, format_dispatch_call(entry), device
                    )
                ),
            )

        entry.async_on_unload(
            device.on(
                EVENT_LOAD_COMPLETE,
                lambda _: _async_add_device_if_started(device),
            )
        )

    entry.async_on_unload(client.on(EVENT_DEVICE_DISCOVERED, _async_device_discovered))

    try:
        await client.start_listening()
    except ListenerError as ex:
        raise ConfigEntryNotReady from ex

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _async_handle_ha_shutdown(event: Event) -> None:
        """Handle HA shutdown."""
        await client.stop_listening()

    entry.async_on_unload(
        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, _async_handle_ha_shutdown)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        client: WeatherFlowListener = hass.data[DOMAIN].pop(entry.entry_id, None)
        if client:
            await client.stop_listening()

    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    client: WeatherFlowListener = hass.data[DOMAIN][config_entry.entry_id]
    return not any(
        identifier
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN
        for device in client.devices
        if device.serial_number == identifier[1]
    )
