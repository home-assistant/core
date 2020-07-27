"""Support for KEBA charging station binary sensors."""
import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_PLUG,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_SAFETY,
    BinarySensorEntity,
)

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the KEBA charging station platform."""
    if discovery_info is None:
        return

    keba = hass.data[DOMAIN]

    sensors = [
        KebaBinarySensor(
            keba, "Online", "Status", "device_state", DEVICE_CLASS_CONNECTIVITY
        ),
        KebaBinarySensor(keba, "Plug", "Plug", "plug_state", DEVICE_CLASS_PLUG),
        KebaBinarySensor(
            keba, "State", "Charging State", "charging_state", DEVICE_CLASS_POWER
        ),
        KebaBinarySensor(
            keba, "Tmo FS", "Failsafe Mode", "failsafe_mode_state", DEVICE_CLASS_SAFETY
        ),
    ]
    async_add_entities(sensors)


class KebaBinarySensor(BinarySensorEntity):
    """Representation of a binary sensor of a KEBA charging station."""

    def __init__(self, keba, key, name, entity_type, device_class):
        """Initialize the KEBA Sensor."""
        self._key = key
        self._keba = keba
        self._name = name
        self._entity_type = entity_type
        self._device_class = device_class
        self._is_on = None
        self._attributes = {}

    @property
    def should_poll(self):
        """Deactivate polling. Data updated by KebaHandler."""
        return False

    @property
    def unique_id(self):
        """Return the unique ID of the binary sensor."""
        return f"{self._keba.device_id}_{self._entity_type}"

    @property
    def name(self):
        """Return the name of the device."""
        return f"{self._keba.device_name} {self._name}"

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._is_on

    @property
    def device_state_attributes(self):
        """Return the state attributes of the binary sensor."""
        return self._attributes

    async def async_update(self):
        """Get latest cached states from the device."""
        if self._key == "Online":
            self._is_on = self._keba.get_value(self._key)

        elif self._key == "Plug":
            self._is_on = self._keba.get_value("Plug_plugged")
            self._attributes["plugged_on_wallbox"] = self._keba.get_value(
                "Plug_wallbox"
            )
            self._attributes["plug_locked"] = self._keba.get_value("Plug_locked")
            self._attributes["plugged_on_EV"] = self._keba.get_value("Plug_EV")

        elif self._key == "State":
            self._is_on = self._keba.get_value("State_on")
            self._attributes["status"] = self._keba.get_value("State_details")
            self._attributes["max_charging_rate"] = str(
                self._keba.get_value("Max curr")
            )

        elif self._key == "Tmo FS":
            self._is_on = not self._keba.get_value("FS_on")
            self._attributes["failsafe_timeout"] = str(self._keba.get_value("Tmo FS"))
            self._attributes["fallback_current"] = str(self._keba.get_value("Curr FS"))
        elif self._key == "Authreq":
            self._is_on = self._keba.get_value(self._key) == 0

    def update_callback(self):
        """Schedule a state update."""
        self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Add update callback after being added to hass."""
        self._keba.add_update_listener(self.update_callback)
