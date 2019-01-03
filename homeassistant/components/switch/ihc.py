"""IHC switch platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.ihc/
"""
from homeassistant.components.ihc import (
    IHC_DATA, IHC_CONTROLLER, IHC_INFO)
from homeassistant.components.ihc.ihcdevice import IHCDevice
from homeassistant.components.switch import SwitchDevice

DEPENDENCIES = ['ihc']


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the IHC switch platform."""
    if discovery_info is None:
        return
    devices = []
    for name, device in discovery_info.items():
        ihc_id = device['ihc_id']
        product = device['product']
        # Find controller that corresponds with device id
        ctrl_id = device['ctrl_id']
        ihc_key = IHC_DATA.format(ctrl_id)
        info = hass.data[ihc_key][IHC_INFO]
        ihc_controller = hass.data[ihc_key][IHC_CONTROLLER]

        switch = IHCSwitch(ihc_controller, name, ihc_id, info, product)
        devices.append(switch)
    add_entities(devices)


class IHCSwitch(IHCDevice, SwitchDevice):
    """IHC Switch."""

    def __init__(self, ihc_controller, name: str, ihc_id: int,
                 info: bool, product=None) -> None:
        """Initialize the IHC switch."""
        super().__init__(ihc_controller, name, ihc_id, product)
        self._state = False

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self.ihc_controller.set_runtime_value_bool(self.ihc_id, True)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self.ihc_controller.set_runtime_value_bool(self.ihc_id, False)

    def on_ihc_change(self, ihc_id, value):
        """Handle IHC resource change."""
        self._state = value
        self.schedule_update_ha_state()
