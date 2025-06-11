"""Get data from Smart Weather station via UDP."""

from __future__ import annotations

from pyweatherflowudp.client import EVENT_DEVICE_DISCOVERED, WeatherFlowListener
from pyweatherflowudp.device import (
    EVENT_LOAD_COMPLETE,
    EVENT_RAIN_START,
    EVENT_STRIKE,
    WeatherFlowDevice,
)
from pyweatherflowudp.errors import ListenerError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.start import async_at_started

from .const import DOMAIN, LOGGER, RAIN_START_EVENT, STRIKE_EVENT, format_dispatch_call

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

        # Setup event listeners for rain and lightning
        @callback
        def _handle_rain_start(data):
            """Handle rain start event from the weather station."""
            LOGGER.debug("Rain detected by device %s", device.serial_number)
            # Fire event on Home Assistant event bus
            hass.bus.async_fire(
                RAIN_START_EVENT,
                {
                    "device_id": device.serial_number,
                    "device_name": device.name
                    if hasattr(device, "name")
                    else device.serial_number,
                    "timestamp": data.get("timestamp")
                    if isinstance(data, dict)
                    else None,
                },
            )

        @callback
        def _handle_strike(data):
            """Handle lightning strike event from the weather station."""
            LOGGER.debug("Lightning strike detected by device %s", device.serial_number)
            # Extract strike data if available
            strike_data = {
                "device_id": device.serial_number,
                "device_name": device.name
                if hasattr(device, "name")
                else device.serial_number,
            }

            # Add strike-specific data if available
            if isinstance(data, dict):
                if "distance" in data:
                    strike_data["distance"] = data["distance"]
                if "energy" in data:
                    strike_data["energy"] = data["energy"]
                if "timestamp" in data:
                    strike_data["timestamp"] = data["timestamp"]

            # Fire event on Home Assistant event bus
            hass.bus.async_fire(STRIKE_EVENT, strike_data)

        # Register event listeners
        entry.async_on_unload(device.on(EVENT_RAIN_START, _handle_rain_start))
        entry.async_on_unload(device.on(EVENT_STRIKE, _handle_strike))

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
