"""Support for Wink binary sensors."""
import logging

import pywink

from homeassistant.components.binary_sensor import BinarySensorEntity

from . import DOMAIN, WinkDevice

_LOGGER = logging.getLogger(__name__)

# These are the available sensors mapped to binary_sensor class
SENSOR_TYPES = {
    "brightness": "light",
    "capturing_audio": "sound",
    "capturing_video": None,
    "co_detected": "gas",
    "liquid_detected": "moisture",
    "loudness": "sound",
    "motion": "motion",
    "noise": "sound",
    "opened": "opening",
    "presence": "occupancy",
    "smoke_detected": "smoke",
    "vibration": "vibration",
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Wink binary sensor platform."""

    for sensor in pywink.get_sensors():
        _id = sensor.object_id() + sensor.name()
        if _id not in hass.data[DOMAIN]["unique_ids"]:
            if sensor.capability() in SENSOR_TYPES:
                add_entities([WinkBinarySensorEntity(sensor, hass)])

    for key in pywink.get_keys():
        _id = key.object_id() + key.name()
        if _id not in hass.data[DOMAIN]["unique_ids"]:
            add_entities([WinkBinarySensorEntity(key, hass)])

    for sensor in pywink.get_smoke_and_co_detectors():
        _id = sensor.object_id() + sensor.name()
        if _id not in hass.data[DOMAIN]["unique_ids"]:
            add_entities([WinkSmokeDetector(sensor, hass)])

    for hub in pywink.get_hubs():
        _id = hub.object_id() + hub.name()
        if _id not in hass.data[DOMAIN]["unique_ids"]:
            add_entities([WinkHub(hub, hass)])

    for remote in pywink.get_remotes():
        _id = remote.object_id() + remote.name()
        if _id not in hass.data[DOMAIN]["unique_ids"]:
            add_entities([WinkRemote(remote, hass)])

    for button in pywink.get_buttons():
        _id = button.object_id() + button.name()
        if _id not in hass.data[DOMAIN]["unique_ids"]:
            add_entities([WinkButton(button, hass)])

    for gang in pywink.get_gangs():
        _id = gang.object_id() + gang.name()
        if _id not in hass.data[DOMAIN]["unique_ids"]:
            add_entities([WinkGang(gang, hass)])

    for door_bell_sensor in pywink.get_door_bells():
        _id = door_bell_sensor.object_id() + door_bell_sensor.name()
        if _id not in hass.data[DOMAIN]["unique_ids"]:
            add_entities([WinkBinarySensorEntity(door_bell_sensor, hass)])

    for camera_sensor in pywink.get_cameras():
        _id = camera_sensor.object_id() + camera_sensor.name()
        if _id not in hass.data[DOMAIN]["unique_ids"]:
            try:
                if camera_sensor.capability() in SENSOR_TYPES:
                    add_entities([WinkBinarySensorEntity(camera_sensor, hass)])
            except AttributeError:
                _LOGGER.info("Device isn't a sensor, skipping")


class WinkBinarySensorEntity(WinkDevice, BinarySensorEntity):
    """Representation of a Wink binary sensor."""

    def __init__(self, wink, hass):
        """Initialize the Wink binary sensor."""
        super().__init__(wink, hass)
        if hasattr(self.wink, "unit"):
            self._unit_of_measurement = self.wink.unit()
        else:
            self._unit_of_measurement = None
        if hasattr(self.wink, "capability"):
            self.capability = self.wink.capability()
        else:
            self.capability = None

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.hass.data[DOMAIN]["entities"]["binary_sensor"].append(self)

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.wink.state()

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return SENSOR_TYPES.get(self.capability)

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return super().device_state_attributes


class WinkSmokeDetector(WinkBinarySensorEntity):
    """Representation of a Wink Smoke detector."""

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        _attributes = super().device_state_attributes
        _attributes["test_activated"] = self.wink.test_activated()
        return _attributes


class WinkHub(WinkBinarySensorEntity):
    """Representation of a Wink Hub."""

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        _attributes = super().device_state_attributes
        _attributes["update_needed"] = self.wink.update_needed()
        _attributes["firmware_version"] = self.wink.firmware_version()
        _attributes["pairing_mode"] = self.wink.pairing_mode()
        _kidde_code = self.wink.kidde_radio_code()
        if _kidde_code is not None:
            # The service call to set the Kidde code
            # takes a string of 1s and 0s so it makes
            # sense to display it to the user that way
            _formatted_kidde_code = f"{_kidde_code:b}".zfill(8)
            _attributes["kidde_radio_code"] = _formatted_kidde_code
        return _attributes


class WinkRemote(WinkBinarySensorEntity):
    """Representation of a Wink Lutron Connected bulb remote."""

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        _attributes = super().device_state_attributes
        _attributes["button_on_pressed"] = self.wink.button_on_pressed()
        _attributes["button_off_pressed"] = self.wink.button_off_pressed()
        _attributes["button_up_pressed"] = self.wink.button_up_pressed()
        _attributes["button_down_pressed"] = self.wink.button_down_pressed()
        return _attributes

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return None


class WinkButton(WinkBinarySensorEntity):
    """Representation of a Wink Relay button."""

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        _attributes = super().device_state_attributes
        _attributes["pressed"] = self.wink.pressed()
        _attributes["long_pressed"] = self.wink.long_pressed()
        return _attributes


class WinkGang(WinkBinarySensorEntity):
    """Representation of a Wink Relay gang."""

    @property
    def is_on(self):
        """Return true if the gang is connected."""
        return self.wink.state()
