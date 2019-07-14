"""Support for ISY994 switches."""
import logging
from typing import Callable

from homeassistant.components.switch import DOMAIN, SwitchDevice
from homeassistant.const import (
    CONF_ICON, CONF_ID, CONF_NAME, CONF_PAYLOAD_OFF, CONF_PAYLOAD_ON,
    CONF_TYPE)
from homeassistant.helpers.typing import ConfigType, Dict

from . import ISYDevice
from .const import ISY994_NODES, ISY994_PROGRAMS, ISY994_VARIABLES

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config: ConfigType,
                   add_entities: Callable[[list], None], discovery_info=None):
    """Set up the ISY994 switch platform."""
    devices = []
    for node in hass.data[ISY994_NODES][DOMAIN]:
        devices.append(ISYSwitchDevice(node))

    for name, status, actions in hass.data[ISY994_PROGRAMS][DOMAIN]:
        devices.append(ISYSwitchProgram(name, status, actions))

    for vcfg, vname, vobj in hass.data[ISY994_VARIABLES][DOMAIN]:
        devices.append(ISYSwitchVariableDevice(vcfg, vname, vobj))

    add_entities(devices)


class ISYSwitchDevice(ISYDevice, SwitchDevice):
    """Representation of an ISY994 switch device."""

    @property
    def is_on(self) -> bool:
        """Get whether the ISY994 device is in the on state."""
        return bool(self.value)

    def turn_off(self, **kwargs) -> None:
        """Send the turn off command to the ISY994 switch."""
        if not self._node.off():
            _LOGGER.debug('Unable to turn off switch.')

    def turn_on(self, **kwargs) -> None:
        """Send the turn oon command to the ISY994 switch."""
        if not self._node.on():
            _LOGGER.debug('Unable to turn on switch.')


class ISYSwitchProgram(ISYSwitchDevice):
    """A representation of an ISY994 program switch."""

    def __init__(self, name: str, node, actions) -> None:
        """Initialize the ISY994 switch program."""
        super().__init__(node)
        self._name = name
        self._actions = actions

    @property
    def is_on(self) -> bool:
        """Get whether the ISY994 switch program is on."""
        return bool(self.value)

    def turn_on(self, **kwargs) -> None:
        """Send the turn on command to the ISY994 switch program."""
        if not self._actions.runThen():
            _LOGGER.error('Unable to turn on switch')

    def turn_off(self, **kwargs) -> None:
        """Send the turn off command to the ISY994 switch program."""
        if not self._actions.runElse():
            _LOGGER.error('Unable to turn off switch')


class ISYSwitchVariableDevice(ISYDevice, SwitchDevice):
    """Representation of an ISY994 variable as a sensor device."""

    def __init__(self, vcfg: dict, vname: str, vobj: object) -> None:
        """Initialize the ISY994 binary sensor program."""
        super().__init__(vobj)
        self._config = vcfg
        self._name = vcfg.get(CONF_NAME, vname)
        self._vtype = vcfg.get(CONF_TYPE)
        self._vid = vcfg.get(CONF_ID)
        self._on_value = vcfg.get(CONF_PAYLOAD_ON)
        self._off_value = vcfg.get(CONF_PAYLOAD_OFF)
        self._change_handler = None
        self._init_change_handler = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to the node change events."""
        self._change_handler = self._node.val.subscribe(
            'changed', self.on_update)
        self._init_change_handler = self._node.init.subscribe(
            'changed', self.on_update)

    @property
    def value(self) -> int:
        """Get the current value of the device."""
        return int(self._node.val)

    @property
    def device_state_attributes(self) -> Dict:
        """Get the state attributes for the device."""
        attr = {}
        attr['init_value'] = int(self._node.init)
        return attr

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        if self.value == self._on_value:
            return True
        if self.value == self._off_value:
            return False
        return None

    @property
    def icon(self):
        """Return the icon."""
        return self._config.get(CONF_ICON)

    def turn_off(self, **kwargs) -> None:
        """Send the turn on command to the ISY994 switch."""
        self._node.setValue(self._off_value)

    def turn_on(self, **kwargs) -> None:
        """Send the turn off command to the ISY994 switch."""
        self._node.setValue(self._on_value)
