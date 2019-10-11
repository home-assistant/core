"""Support to control a Zehnder ComfoAir 350 ventilation unit."""

import logging
import voluptuous as vol

from homeassistant.const import CONF_NAME
from homeassistant.helpers import discovery
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
import homeassistant.helpers.config_validation as cv
from comfoair.asyncio import ComfoAir

DOMAIN = "comfoair"
SIGNAL_COMFOAIR_UPDATE_RECEIVED = "comfoair_update_received"
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

    async def _ca_service_virtualkey(service):
        ev_mask = service.data.get(ATTR_MASK)
        ev_type = service.data.get(ATTR_TYPE)
        await hass.data[DOMAIN].keypress(ev_mask, ev_type)

    hass.services.async_register(
        DOMAIN,
        SERVICE_VIRTUALKEY,
        _ca_service_virtualkey,
        schema=SCHEMA_SERVICE_VIRTUALKEY,
    )

    return True


class ComfoAirModule:
    """Representation of a ComfoAir component."""

    def __init__(self, hass: HomeAssistantType, config: ConfigType):
        """Initialize the ComfoAir component."""
        self._hass = hass
        self._name = config[DOMAIN].get(CONF_NAME)
        self._cache = {}

        self._ca = ComfoAir(config[DOMAIN].get(CONF_SERIAL_PORT))
        self._ca.add_listener(self._event)

    async def _event(self, event):
        cmd, data = event
        if self._cache.get(cmd) == data:
            return
        self._cache[cmd] = data

        async_dispatcher_send(self._hass, SIGNAL_COMFOAIR_UPDATE_RECEIVED, [cmd, data])

    async def connect(self):
        """Connect to a serial port or socket."""
        await self._ca.connect(self._hass.loop)

    async def stop(self):
        """Close resources."""
        self._ca.remove_listener(self._event)
        self._ca.shutdown()

    async def set_speed(self, speed: int):
        """Set the speed of the fans."""
        await self._ca.set_speed(speed)

    def __getitem__(self, key: int) -> bytes:
        """Access cached data."""
        return self._cache.get(key)

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
