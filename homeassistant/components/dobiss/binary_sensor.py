"""Support for dobiss switches."""
import logging

from dobissapi import DobissBinarySensor

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .const import (
    CONF_IGNORE_ZIGBEE_DEVICES,
    CONF_INVERT_BINARY_SENSOR,
    DOMAIN,
    KEY_API,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up dobiss binary sensor."""

    _LOGGER.debug(f"Setting up binary_sensor component of {DOMAIN}")
    dobiss = hass.data[DOMAIN][config_entry.entry_id][KEY_API].api
    # _LOGGER.warn("set up dobiss switch on {}".format(dobiss.url))

    entities = []
    d_entities = dobiss.get_devices_by_type(DobissBinarySensor)
    for d in d_entities:
        if (
            config_entry.options.get(CONF_IGNORE_ZIGBEE_DEVICES) is not None
            and config_entry.options.get(CONF_IGNORE_ZIGBEE_DEVICES)
            and (d.address in (210, 211))
        ):
            continue
        # _LOGGER.warn("set up dobiss binary sensor on {}".format(dobiss.host))
        entities.append(HADobissBinarySensor(d, config_entry))

    if entities:
        async_add_entities(entities)


class HADobissBinarySensor(BinarySensorEntity):
    """Dobiss Light Sensor."""

    device_class = BinarySensorDeviceClass.DOOR

    should_poll = False

    def __init__(self, dobisssensor: DobissBinarySensor, config_entry):
        """Init dobiss Switch device."""
        super().__init__()
        self._config_entry = config_entry
        self._dobisssensor = dobisssensor

    @property
    def is_on(self):
        """Return the state of the sensor."""
        if self._config_entry.options.get(CONF_INVERT_BINARY_SENSOR):
            return not self._dobisssensor.is_on
        return self._dobisssensor.is_on

    @property
    def device_info(self):
        """Information about this entity/device."""
        return {
            "identifiers": {(DOMAIN, self._dobisssensor.object_id)},
            "name": self.name,
            "manufacturer": "dobiss",
        }

    @property
    def extra_state_attributes(self):
        """Return supported attributes."""
        return self._dobisssensor.attributes

    @property
    def available(self) -> bool:
        """Return True."""
        return True

    # leave the icon up to the class
    #    @property
    #    def icon(self):
    #        """Return the icon to use in the frontend"""
    #        return ICON_FROM_DOBISS[self._dobisssensor.icons_id]

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        self._dobisssensor.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        self._dobisssensor.remove_callback(self.async_write_ha_state)

    @property
    def name(self):
        """Return the display name of this sensor."""
        return self._dobisssensor.name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._dobisssensor.object_id
