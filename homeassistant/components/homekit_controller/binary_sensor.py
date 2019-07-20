"""Support for Homekit motion sensors."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice

from . import KNOWN_DEVICES, HomeKitEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Legacy set up platform."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Homekit lighting."""
    hkid = config_entry.data['AccessoryPairingID']
    conn = hass.data[KNOWN_DEVICES][hkid]

    def async_add_service(aid, service):
        devtype = service['stype']
        info = {'aid': aid, 'iid': service['iid']}
        if devtype == 'motion':
            async_add_entities([HomeKitMotionSensor(conn, info)], True)
            return True

        if devtype == 'contact':
            async_add_entities([HomeKitContactSensor(conn, info)], True)
            return True

        return False

    conn.add_listener(async_add_service)


class HomeKitMotionSensor(HomeKitEntity, BinarySensorDevice):
    """Representation of a Homekit motion sensor."""

    def __init__(self, *args):
        """Initialise the entity."""
        super().__init__(*args)
        self._on = False

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        # pylint: disable=import-error
        from homekit.model.characteristics import CharacteristicsTypes

        return [
            CharacteristicsTypes.MOTION_DETECTED,
        ]

    def _update_motion_detected(self, value):
        self._on = value

    @property
    def device_class(self):
        """Define this binary_sensor as a motion sensor."""
        return 'motion'

    @property
    def is_on(self):
        """Has motion been detected."""
        return self._on

class HomeKitContactSensor(HomeKitEntity, BinarySensorDevice):
    """Representation of a Homekit contact sensor."""

    def __init__(self, *args):
        """Initialise the entity."""
        super().__init__(*args)
        self._state = None

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        # pylint: disable=import-error
        from homekit.model.characteristics import CharacteristicsTypes

        return [
            CharacteristicsTypes.CONTACT_STATE,
        ]

    def _update_contact_state(self, value):
        self._state = value

    @property
    def is_on(self):
        """Return true if the binary sensor is on/open."""
        return self._state
