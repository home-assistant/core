"""
Integration with the Rachio Iro sprinkler system controller.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.rachio/
"""
from abc import abstractmethod
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.rachio import (DOMAIN as DOMAIN_RACHIO,
                                             KEY_DEVICE_ID,
                                             KEY_STATUS,
                                             KEY_SUBTYPE,
                                             SIGNAL_RACHIO_CONTROLLER_UPDATE,
                                             STATUS_OFFLINE,
                                             STATUS_ONLINE,
                                             SUBTYPE_OFFLINE,
                                             SUBTYPE_ONLINE,)
from homeassistant.helpers.dispatcher import dispatcher_connect

DEPENDENCIES = ['rachio']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Rachio binary sensors."""
    devices = []
    for controller in hass.data[DOMAIN_RACHIO].controllers:
        devices.append(RachioControllerOnlineBinarySensor(hass, controller))

    add_entities(devices)
    _LOGGER.info("%d Rachio binary sensor(s) added", len(devices))


class RachioControllerBinarySensor(BinarySensorDevice):
    """Represent a binary sensor that reflects a Rachio state."""

    def __init__(self, hass, controller, poll=True):
        """Set up a new Rachio controller binary sensor."""
        self._controller = controller

        if poll:
            self._state = self._poll_update()
        else:
            self._state = None

        dispatcher_connect(hass, SIGNAL_RACHIO_CONTROLLER_UPDATE,
                           self._handle_any_update)

    @property
    def should_poll(self) -> bool:
        """Declare that this entity pushes its state to HA."""
        return False

    @property
    def is_on(self) -> bool:
        """Return whether the sensor has a 'true' value."""
        return self._state

    def _handle_any_update(self, *args, **kwargs) -> None:
        """Determine whether an update event applies to this device."""
        if args[0][KEY_DEVICE_ID] != self._controller.controller_id:
            # For another device
            return

        # For this device
        self._handle_update()

    @abstractmethod
    def _poll_update(self, data=None) -> bool:
        """Request the state from the API."""
        pass

    @abstractmethod
    def _handle_update(self, *args, **kwargs) -> None:
        """Handle an update to the state of this sensor."""
        pass


class RachioControllerOnlineBinarySensor(RachioControllerBinarySensor):
    """Represent a binary sensor that reflects if the controller is online."""

    def __init__(self, hass, controller):
        """Set up a new Rachio controller online binary sensor."""
        super().__init__(hass, controller, poll=False)
        self._state = self._poll_update(controller.init_data)

    @property
    def name(self) -> str:
        """Return the name of this sensor including the controller name."""
        return "{} online".format(self._controller.name)

    @property
    def unique_id(self) -> str:
        """Return a unique id for this entity."""
        return "{}-online".format(self._controller.controller_id)

    @property
    def device_class(self) -> str:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return 'connectivity'

    @property
    def icon(self) -> str:
        """Return the name of an icon for this sensor."""
        return 'mdi:wifi-strength-4' if self.is_on\
            else 'mdi:wifi-strength-off-outline'

    def _poll_update(self, data=None) -> bool:
        """Request the state from the API."""
        if data is None:
            data = self._controller.rachio.device.get(
                self._controller.controller_id)[1]

        if data[KEY_STATUS] == STATUS_ONLINE:
            return True
        if data[KEY_STATUS] == STATUS_OFFLINE:
            return False
        _LOGGER.warning('"%s" reported in unknown state "%s"', self.name,
                        data[KEY_STATUS])

    def _handle_update(self, *args, **kwargs) -> None:
        """Handle an update to the state of this sensor."""
        if args[0][KEY_SUBTYPE] == SUBTYPE_ONLINE:
            self._state = True
        elif args[0][KEY_SUBTYPE] == SUBTYPE_OFFLINE:
            self._state = False

        self.schedule_update_ha_state()
