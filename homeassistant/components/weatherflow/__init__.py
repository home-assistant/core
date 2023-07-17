"""The WeatherFlow integration."""
from __future__ import annotations

from pyweatherflowudp.client import EVENT_DEVICE_DISCOVERED, WeatherFlowListener
from pyweatherflowudp.const import DEFAULT_HOST
from pyweatherflowudp.device import EVENT_LOAD_COMPLETE, WeatherFlowDevice
from pyweatherflowudp.errors import ListenerError

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import CoreState, Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, LOGGER

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WeatherFlow from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    client = hass.data[DOMAIN][entry.entry_id] = WeatherFlowListener(
        host=entry.data.get(CONF_HOST, DEFAULT_HOST)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def device_discovered(device: WeatherFlowDevice) -> None:
        LOGGER.debug("Found a device: %s", device)

        @callback
        def add_device() -> None:
            async_dispatcher_send(
                hass, f"{DOMAIN}_{entry.entry_id}_add_{SENSOR_DOMAIN}", device
            )

        entry.async_on_unload(
            device.on(
                EVENT_LOAD_COMPLETE,
                lambda _: add_device()
                if hass.state == CoreState.running
                else hass.bus.async_listen_once(
                    EVENT_HOMEASSISTANT_STARTED, lambda _: add_device()
                ),
            )
        )

    entry.async_on_unload(client.on(EVENT_DEVICE_DISCOVERED, device_discovered))

    try:
        await client.start_listening()
    except ListenerError as ex:
        raise ConfigEntryNotReady from ex

    async def handle_ha_shutdown(event: Event) -> None:
        """Handle HA shutdown."""
        await client.stop_listening()

    entry.async_on_unload(
        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, handle_ha_shutdown)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        client: WeatherFlowListener = hass.data[DOMAIN][entry.entry_id]
        await client.stop_listening()
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
