"""Switch platform integration for Numato USB GPIO expanders."""
import logging

from numato_gpio import NumatoGpioError

from homeassistant.const import (
    CONF_DEVICES,
    CONF_ID,
    CONF_SWITCHES,
    DEVICE_DEFAULT_NAME,
)
from homeassistant.helpers.entity import ToggleEntity

from . import CONF_INVERT_LOGIC, CONF_PORTS, DATA_API, DOMAIN

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the configured Numato USB GPIO switch ports."""
    if discovery_info is None:
        return
    switches = []
    devices = hass.data[DOMAIN][CONF_DEVICES]
    for device in [d for d in devices if CONF_SWITCHES in d]:
        device_id = device[CONF_ID]
        platform = device[CONF_SWITCHES]
        invert_logic = platform[CONF_INVERT_LOGIC]
        ports = platform[CONF_PORTS]
        for port, port_name in ports.items():
            switches.append(
                NumatoGpioSwitch(
                    port_name,
                    device_id,
                    port,
                    invert_logic,
                    hass.data[DOMAIN][DATA_API],
                )
            )
    add_entities(switches, True)


class NumatoGpioSwitch(ToggleEntity):
    """Representation of a Numato USB GPIO switch port."""

    def __init__(self, name, device_id, port, invert_logic, api):
        """Initialize the port."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._device_id = device_id
        self._port = port
        self._invert_logic = invert_logic
        self._state = False
        self._api = api

    async def async_added_to_hass(self):
        """Configure the device port as a switch."""
        try:
            await self.hass.async_add_executor_job(
                self._api.setup_output, self._device_id, self._port
            )
            await self.hass.async_add_executor_job(
                self._api.write_output,
                self._device_id,
                self._port,
                1 if self._invert_logic else 0,
            )
        except NumatoGpioError as ex:
            _LOGGER.error(
                "Numato USB device %s port %s failed %s",
                self._device_id,
                self._port,
                str(ex),
            )

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def is_on(self):
        """Return true if port is turned on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the port on."""
        try:
            self._api.write_output(
                self._device_id, self._port, 0 if self._invert_logic else 1
            )
            self._state = True
            self.schedule_update_ha_state()
        except NumatoGpioError as err:
            _LOGGER.error(
                "Failed to turn on Numato device %s port %s: %s",
                self._device_id,
                self._port,
                str(err),
            )

    def turn_off(self, **kwargs):
        """Turn the port off."""
        try:
            self._api.write_output(
                self._device_id, self._port, 1 if self._invert_logic else 0
            )
            self._state = False
            self.schedule_update_ha_state()
        except NumatoGpioError as err:
            _LOGGER.error(
                "Failed to turn off Numato device %s port %s: %s",
                self._device_id,
                self._port,
                str(err),
            )
