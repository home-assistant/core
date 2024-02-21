"""Support for ANEL PwrCtrl switches."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from anel_pwrctrl import Device, DeviceMaster, Switch
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

CONF_PORT_RECV = "port_recv"
CONF_PORT_SEND = "port_send"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PORT_RECV): cv.port,
        vol.Required(CONF_PORT_SEND): cv.port,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_HOST): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up PwrCtrl devices/switches."""
    host = config.get(CONF_HOST)
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    port_recv = config[CONF_PORT_RECV]
    port_send = config[CONF_PORT_SEND]

    try:
        master = DeviceMaster(
            username=username,
            password=password,
            read_port=port_send,
            write_port=port_recv,
        )
        master.query(ip_addr=host)
    except OSError as ex:
        _LOGGER.error("Unable to discover PwrCtrl device: %s", str(ex))
        return

    devices: list[SwitchEntity] = []
    for device in master.devices.values():
        parent_device = PwrCtrlDevice(device)
        devices.extend(
            PwrCtrlSwitch(switch, parent_device) for switch in device.switches.values()
        )

    add_entities(devices)


class PwrCtrlSwitch(SwitchEntity):
    """Representation of a PwrCtrl switch."""

    def __init__(self, port: Switch, parent_device: PwrCtrlDevice) -> None:
        """Initialize the PwrCtrl switch."""
        self._port = port
        self._parent_device = parent_device
        self._attr_unique_id = f"{port.device.host}-{port.get_index()}"
        self._attr_name = port.label

    def update(self) -> None:
        """Trigger update for all switches on the parent device."""
        self._parent_device.update()
        self._attr_is_on = self._port.get_state()

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._port.on()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._port.off()


class PwrCtrlDevice:
    """Device representation for per device throttling."""

    def __init__(self, device: Device) -> None:
        """Initialize the PwrCtrl device."""
        self._device = device

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self) -> None:
        """Update the device and all its switches."""
        self._device.update()
