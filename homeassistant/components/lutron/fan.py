"""Support for Lutron fan."""
from homeassistant.components.fan import ATTR_PERCENTAGE, SUPPORT_SET_SPEED, FanEntity

from . import LUTRON_CONTROLLER, LUTRON_DEVICES, LutronDevice


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Lutron fans."""
    devs = []
    for (area_name, device) in hass.data[LUTRON_DEVICES]["fan"]:
        dev = LutronFan(area_name, device, hass.data[LUTRON_CONTROLLER])
        devs.append(dev)

    add_entities(devs, True)


class LutronFan(LutronDevice, FanEntity):
    """Representation of a Lutron Fan."""

    def __init__(self, area_name, lutron_device, controller):
        """Initialize the light."""
        self._prev_percentage = None
        super().__init__(area_name, lutron_device, controller)

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_SET_SPEED

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return 4

    @property
    def percentage(self) -> int:
        """Return the speed percentage of the fan."""
        new_percentage = self._lutron_device.last_level()
        if new_percentage != 0:
            self._prev_percentage = new_percentage
        return new_percentage

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {"lutron_integration_id": self._lutron_device.id}

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._lutron_device.last_level() > 0

    def update(self):
        """Call when forcing a refresh of the device."""
        if self._prev_percentage is None:
            self._prev_percentage = self._lutron_device.level

    def turn_on(self, **kwargs):
        """Turn the fan on."""
        if ATTR_PERCENTAGE in kwargs and kwargs[ATTR_PERCENTAGE] is not None:
            new_percentage = kwargs[ATTR_PERCENTAGE]
        elif self._prev_percentage is None or self._prev_percentage == 0:
            new_percentage = 100
        else:
            new_percentage = self._prev_percentage
        self._prev_percentage = new_percentage
        self._lutron_device.level = new_percentage

    def turn_off(self, **kwargs):
        """Turn the fan off."""
        self._lutron_device.level = 0

    def set_percentage(self, percentage: int):
        """Set the speed percentage of the fan."""
        self._prev_percentage = percentage
        self._lutron_device.level = percentage
