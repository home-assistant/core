"""
homeassistant.helpers.device
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides ABC for devices in HA.
"""

from homeassistant import NoEntitySpecifiedError

from homeassistant.const import (
    ATTR_FRIENDLY_NAME, STATE_ON, STATE_OFF, DEVICE_DEFAULT_NAME)


class Device(object):
    """ ABC for Home Assistant devices. """
    # pylint: disable=no-self-use

    hass = None
    entity_id = None

    @property
    def should_poll(self):
        """
        Return True if device has to be polled for state.
        False if device pushes its state to HA.
        """
        return True

    @property
    def unique_id(self):
        """ Returns a unique id. """
        return "{}.{}".format(self.__class__, id(self))

    @property
    def name(self):
        """ Returns the name of the device. """
        return self.get_name()

    @property
    def state(self):
        """ Returns the state of the device. """
        return self.get_state()

    @property
    def state_attributes(self):
        """ Returns the state attributes. """
        return {}

    # DEPRECATION NOTICE:
    # Device is moving from getters to properties.
    # For now the new properties will call the old functions
    # This will be removed in the future.

    def get_name(self):
        """ Returns the name of the device if any. """
        return DEVICE_DEFAULT_NAME

    def get_state(self):
        """ Returns state of the device. """
        return "Unknown"

    def get_state_attributes(self):
        """ Returns optional state attributes. """
        return None

    def update(self):
        """ Retrieve latest state from the real device. """
        pass

    def update_ha_state(self, force_refresh=False):
        """
        Updates Home Assistant with current state of device.
        If force_refresh == True will update device before setting state.
        """
        if self.hass is None:
            raise RuntimeError("Attribute hass is None for {}".format(self))

        if self.entity_id is None:
            raise NoEntitySpecifiedError(
                "No entity specified for device {}".format(self.name))

        if force_refresh:
            self.update()

        attr = self.state_attributes or {}

        if ATTR_FRIENDLY_NAME not in attr and self.name:
            attr[ATTR_FRIENDLY_NAME] = self.name

        return self.hass.states.set(self.entity_id, self.state, attr)

    def __eq__(self, other):
        return (isinstance(other, Device) and
                other.unique_id == self.unique_id)

    def __repr__(self):
        return "<Device {}: {}>".format(self.name, self.state)


class ToggleDevice(Device):
    """ ABC for devices that can be turned on and off. """
    # pylint: disable=no-self-use

    @property
    def state(self):
        """ Returns the state. """
        return STATE_ON if self.is_on else STATE_OFF

    @property
    def is_on(self):
        """ True if device is on. """
        return False

    def turn_on(self, **kwargs):
        """ Turn the device on. """
        pass

    def turn_off(self, **kwargs):
        """ Turn the device off. """
        pass
