"""Support to control a Zehnder ComfoAir 350 ventilation unit."""

import asyncio
import logging
from typing import Any, Dict, Optional

from comfoair.asyncio import ComfoAir
import voluptuous as vol

from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import CONF_SERIAL_PORT, DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_SERIAL_PORT): cv.string,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_VIRTUALKEY = "virtualkey"
ATTR_MASK = "mask"
ATTR_TYPE = "type"
CA_PRESS_EVENTS = ["PRESS_SHORT", "PRESS_LONG"]
PLATFORMS = [FAN_DOMAIN, SENSOR_DOMAIN]

SCHEMA_SERVICE_VIRTUALKEY = vol.Schema(
    {
        vol.Required(ATTR_MASK): vol.In(range(1, 64)),
        vol.Optional(ATTR_TYPE, default=CA_PRESS_EVENTS[0]): vol.In(CA_PRESS_EVENTS),
    }
)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up the ComfoAir component."""
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up a ComfoAir entry."""
    if DOMAIN in hass.data:
        _LOGGER.error("Sorry, only one ComfoAir supported for now")
        return False

    conf = entry.data
    hass.data[DOMAIN] = ComfoAirModule(hass, conf[CONF_NAME], conf[CONF_SERIAL_PORT])
    await hass.data[DOMAIN].connect()

    for domain in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, domain)
        )

    async def ca_service_virtualkey(service):
        ev_mask = service.data[ATTR_MASK]
        ev_type = service.data[ATTR_TYPE]
        await hass.data[DOMAIN].keypress(ev_mask, ev_type)

    hass.services.async_register(
        DOMAIN,
        SERVICE_VIRTUALKEY,
        ca_service_virtualkey,
        schema=SCHEMA_SERVICE_VIRTUALKEY,
    )

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, hass.data[DOMAIN].stop)

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )

    await hass.data[DOMAIN].stop()

    return unload_ok


class ComfoAirModule:
    """Representation of a ComfoAir component."""

    def __init__(self, hass: HomeAssistantType, name: str, port: str):
        """Initialize the ComfoAir component."""
        self._hass = hass
        self._name = name
        self._ca = ComfoAir(port)
        self._device_info = {
            "identifiers": {(port,)},
            "name": name,
            "manufacturer": "Zehnder",
            "model": "ComfoAir 350",
        }

    async def connect(self):
        """Connect to a serial port or socket."""
        await self._ca.connect(self._hass.loop)

    async def stop(self, event: Event):
        """Close resources."""
        await self._ca.shutdown()

    async def set_speed(self, speed: int):
        """Set the speed of the fans."""
        await self._ca.set_speed(speed)

    @property
    def device_info(self) -> Optional[Dict[str, Any]]:
        """Return device specific attributes."""
        return self._device_info

    @property
    def name(self):
        """Access configured name of ventilation unit."""
        return self._name

    async def keypress(self, ev_mask: int, ev_type: str):
        """Simulate a keypress."""
        if ev_type == "PRESS_LONG":
            millis = 1000
        else:
            millis = 100

        await self._ca.emulate_keypress(ev_mask, millis)

    def add_cooked_listener(self, attr, callback):
        """Register a callback for a sensor value."""
        return self._ca.add_cooked_listener(attr, callback)

    def remove_cooked_listener(self, attr, callback):
        """Unregister a callback for a sensor value."""
        return self._ca.remove_cooked_listener(attr, callback)
