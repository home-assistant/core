"""Base class for multi level switches in devolo Home Control."""

from devolo_home_control_api.devices.zwave import Zwave
from devolo_home_control_api.homecontrol import HomeControl

from .devolo_device import DevoloDeviceEntity


class DevoloMultiLevelSwitchDeviceEntity(DevoloDeviceEntity):
    """Representation of a multi level switch device within devolo Home Control. Something like a dimmer or a thermostat."""

    _attr_name = None

    def __init__(
        self, homecontrol: HomeControl, device_instance: Zwave, element_uid: str
    ) -> None:
        """Initialize a multi level switch within devolo Home Control."""
        super().__init__(
            homecontrol=homecontrol,
            device_instance=device_instance,
            element_uid=element_uid,
        )
        self._multi_level_switch_property = device_instance.multi_level_switch_property[
            element_uid
        ]

        self._value = self._multi_level_switch_property.value
