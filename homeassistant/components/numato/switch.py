"""Switch platform integration for Numato USB GPIO expanders."""
from __future__ import annotations

import logging

from numato_gpio import NumatoGpioError

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import (
    CONF_DEVICES,
    CONF_ID,
    CONF_SWITCHES,
    DEVICE_DEFAULT_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import CONF_INVERT_LOGIC, CONF_PORTS, DATA_API, DOMAIN

_LOGGER = logging.getLogger(__name__)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the configured Numato USB GPIO switch ports."""
    if discovery_info is None:
        return

    api = hass.data[DOMAIN][DATA_API]
    switches = []
    devices = hass.data[DOMAIN][CONF_DEVICES]
    for device in [d for d in devices if CONF_SWITCHES in d]:
        device_id = device[CONF_ID]
        platform = device[CONF_SWITCHES]
        invert_logic = platform[CONF_INVERT_LOGIC]
        ports = platform[CONF_PORTS]
        for port, port_name in ports.items():
            try:
                api.setup_output(device_id, port)
                api.write_output(device_id, port, 1 if invert_logic else 0)
            except NumatoGpioError as err:
                _LOGGER.error(
                    "Failed to initialize switch '%s' on Numato device %s port %s: %s",
                    port_name,
                    device_id,
                    port,
                    err,
                )
                continue
            switches.append(
                NumatoGpioSwitch(
                    port_name,
                    device_id,
                    port,
                    invert_logic,
                    api,
                )
            )
    add_entities(switches, True)


class NumatoGpioSwitch(SwitchEntity):
    """Representation of a Numato USB GPIO switch port."""

    _attr_should_poll = False

    def __init__(self, name, device_id, port, invert_logic, api):
        """Initialize the port."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._device_id = device_id
        self._port = port
        self._invert_logic = invert_logic
        self._state = False
        self._api = api

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

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
                err,
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
                err,
            )
