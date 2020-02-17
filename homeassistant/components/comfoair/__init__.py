"""Support to control a Zehnder ComfoAir 350 ventilation unit."""

import logging

from comfoair.asyncio import ComfoAir
import voluptuous as vol

from homeassistant.const import CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

DOMAIN = "comfoair"
CONF_SERIAL_PORT = "serial_port"
DEFAULT_NAME = "ComfoAir"

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

SCHEMA_SERVICE_VIRTUALKEY = vol.Schema(
    {
        vol.Required(ATTR_MASK): vol.In(range(1, 64)),
        vol.Optional(ATTR_TYPE, default=CA_PRESS_EVENTS[0]): vol.In(CA_PRESS_EVENTS),
    }
)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up the ComfoAir component."""
    hass.data[DOMAIN] = ComfoAirModule(hass, config)
    await hass.data[DOMAIN].connect()

    for com in ["fan", "sensor"]:
        coro = discovery.async_load_platform(hass, com, DOMAIN, {}, config)
        hass.async_create_task(coro)

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


class ComfoAirModule:
    """Representation of a ComfoAir component."""

    def __init__(self, hass: HomeAssistantType, config: ConfigType):
        """Initialize the ComfoAir component."""
        self._hass = hass
        self._name = config[DOMAIN][CONF_NAME]
        self._ca = ComfoAir(config[DOMAIN][CONF_SERIAL_PORT])

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
