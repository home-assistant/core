"""
Support for Blink system camera control.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/blink/
"""
from homeassistant.components import blink
from homeassistant.components.switch import SwitchDevice

DEPENDENCIES = ['blink']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup a Blink camera's controls."""
    data = blink.BLINKGLOB.blink

    for name in data.cameras.keys():
        add_devices([BlinkSwitch(name, data, 'snap_picture')])
        add_devices([BlinkSwitch(name, data, 'motion')])

    add_devices([BlinkArmSystem(data)])


class BlinkSwitch(SwitchDevice):
    """A class for switches to control Blink camera."""

    def __init__(self, name, data, switch_type):
        """A method to initialize camera control."""
        self._name = 'blink ' + name + ' ' + switch_type
        self._camera_name = name
        self.data = data
        self._type = switch_type
        if self._type == 'motion':
            self._state = self.data.cameras[self._camera_name].armed == 'armed'
        elif self._type == 'snap_picture':
            self._state = False
        else:
            self._state = None

    @property
    def name(self):
        """A method to return the name of the camera."""
        return self._name.replace(" ", "_")

    @property
    def is_on(self):
        """A method to check the state of the control switch."""
        return self._state

    def turn_on(self, **kwargs):
        """A method to enable the switch."""
        camera = self.data.cameras[self._camera_name]
        if self._type == 'motion':
            camera.set_motion_detect(True)
            self._state = True
        elif self._type == 'snap_picture':
            camera.snap_picture()
            self.turn_off()
        else:
            self._state = None

    def turn_off(self, **kwargs):
        """A method to disable the switch."""
        camera = self.data.cameras[self._camera_name]
        if self._type == 'motion':
            camera.set_motion_detect(False)
            self._state = False
        elif self._type == 'snap_picture':
            self._state = False
        else:
            self._state = None


class BlinkArmSystem(SwitchDevice):
    """A switch class to arm Blink System."""

    def __init__(self, data):
        """A method to initialize system control."""
        self._name = 'blink_arm_system'
        self.data = data
        self._state = self.data.arm

    @property
    def name(self):
        """A method to return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """A method to check the state of the control switch."""
        return self._state

    def turn_on(self, **kwargs):
        """A method to enable the switch."""
        self.data.arm = True
        self._state = True

    def turn_off(self, **kwargs):
        """A method to disable the switch."""
        self.data.arm = False
        self._state = False
