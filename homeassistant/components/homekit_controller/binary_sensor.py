"""Support for Homekit motion sensors."""
import logging

from homekit.model.characteristics import CharacteristicsTypes

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_SMOKE,
    BinarySensorDevice,
)
from homeassistant.core import callback

from . import KNOWN_DEVICES, HomeKitEntity

_LOGGER = logging.getLogger(__name__)


class HomeKitMotionSensor(HomeKitEntity, BinarySensorDevice):
    """Representation of a Homekit motion sensor."""

    def __init__(self, *args):
        """Initialise the entity."""
        super().__init__(*args)
        self._on = False

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.MOTION_DETECTED]

    def _update_motion_detected(self, value):
        self._on = value

    @property
    def device_class(self):
        """Define this binary_sensor as a motion sensor."""
        return "motion"

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
        return [CharacteristicsTypes.CONTACT_STATE]

    def _update_contact_state(self, value):
        self._state = value

    @property
    def is_on(self):
        """Return true if the binary sensor is on/open."""
        return self._state == 1


class HomeKitSmokeSensor(HomeKitEntity, BinarySensorDevice):
    """Representation of a Homekit smoke sensor."""

    def __init__(self, *args):
        """Initialise the entity."""
        super().__init__(*args)
        self._state = None

    @property
    def device_class(self) -> str:
        """Return the class of this sensor."""
        return DEVICE_CLASS_SMOKE

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.SMOKE_DETECTED]

    def _update_smoke_detected(self, value):
        self._state = value

    @property
    def is_on(self):
        """Return true if smoke is currently detected."""
        return self._state == 1


ENTITY_TYPES = {
    "motion": HomeKitMotionSensor,
    "contact": HomeKitContactSensor,
    "smoke": HomeKitSmokeSensor,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Homekit lighting."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(aid, service):
        entity_class = ENTITY_TYPES.get(service["stype"])
        if not entity_class:
            return False
        info = {"aid": aid, "iid": service["iid"]}
        async_add_entities([entity_class(conn, info)], True)
        return True

    conn.add_listener(async_add_service)
