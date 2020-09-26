"""Support for deCONZ binary sensors."""
from pydeconz.sensor import CarbonMonoxide, Fire, OpenClose, Presence, Vibration, Water

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_OPENING,
    DEVICE_CLASS_SMOKE,
    DEVICE_CLASS_VIBRATION,
    DOMAIN,
    BinarySensorEntity,
)
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import ATTR_DARK, ATTR_ON, NEW_SENSOR
from .deconz_device import DeconzDevice
from .gateway import get_gateway_from_config_entry

ATTR_ORIENTATION = "orientation"
ATTR_TILTANGLE = "tiltangle"
ATTR_VIBRATIONSTRENGTH = "vibrationstrength"

DEVICE_CLASS = {
    CarbonMonoxide: DEVICE_CLASS_GAS,
    Fire: DEVICE_CLASS_SMOKE,
    OpenClose: DEVICE_CLASS_OPENING,
    Presence: DEVICE_CLASS_MOTION,
    Vibration: DEVICE_CLASS_VIBRATION,
    Water: DEVICE_CLASS_MOISTURE,
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old way of setting up deCONZ platforms."""


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the deCONZ binary sensor."""
    gateway = get_gateway_from_config_entry(hass, config_entry)
    gateway.entities[DOMAIN] = set()

    @callback
    def async_add_sensor(sensors):
        """Add binary sensor from deCONZ."""
        entities = []

        for sensor in sensors:

            if (
                sensor.BINARY
                and sensor.uniqueid not in gateway.entities[DOMAIN]
                and (
                    gateway.option_allow_clip_sensor
                    or not sensor.type.startswith("CLIP")
                )
            ):
                entities.append(DeconzBinarySensor(sensor, gateway))

        async_add_entities(entities, True)

    gateway.listeners.append(
        async_dispatcher_connect(
            hass, gateway.async_signal_new_device(NEW_SENSOR), async_add_sensor
        )
    )

    async_add_sensor(
        [gateway.api.sensors[key] for key in sorted(gateway.api.sensors, key=int)]
    )


class DeconzBinarySensor(DeconzDevice, BinarySensorEntity):
    """Representation of a deCONZ binary sensor."""

    TYPE = DOMAIN

    @callback
    def async_update_callback(self, force_update=False, ignore_update=False):
        """Update the sensor's state."""
        if ignore_update:
            return

        keys = {"on", "reachable", "state"}
        if force_update or self._device.changed_keys.intersection(keys):
            self.async_write_ha_state()

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._device.is_tripped

    @property
    def device_class(self):
        """Return the class of the sensor."""
        return DEVICE_CLASS.get(type(self._device))

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        attr = {}

        if self._device.on is not None:
            attr[ATTR_ON] = self._device.on

        if self._device.secondary_temperature is not None:
            attr[ATTR_TEMPERATURE] = self._device.secondary_temperature

        if self._device.type in Presence.ZHATYPE:

            if self._device.dark is not None:
                attr[ATTR_DARK] = self._device.dark

        elif self._device.type in Vibration.ZHATYPE:
            attr[ATTR_ORIENTATION] = self._device.orientation
            attr[ATTR_TILTANGLE] = self._device.tiltangle
            attr[ATTR_VIBRATIONSTRENGTH] = self._device.vibrationstrength

        return attr
