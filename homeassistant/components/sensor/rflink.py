"""
Support for Rflink sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.rflink/
"""
import asyncio
from functools import partial
import logging

from homeassistant.components import group
from homeassistant.components.rflink import (
    CONF_ALIASSES, CONF_DEVICES, CONF_NEW_DEVICES_GROUP, DATA_DEVICE_REGISTER,
    DATA_ENTITY_LOOKUP, DOMAIN, EVENT_KEY_ID, EVENT_KEY_SENSOR, EVENT_KEY_UNIT,
    RflinkDevice, cv, vol)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT, CONF_NAME, CONF_PLATFORM,
    CONF_UNIT_OF_MEASUREMENT)

DEPENDENCIES = ['rflink']

_LOGGER = logging.getLogger(__name__)

SENSOR_ICONS = {
    'humidity': 'mdi:water-percent',
    'battery': 'mdi:battery',
    'temperature': 'mdi:thermometer',
}

CONF_SENSOR_TYPE = 'sensor_type'

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): DOMAIN,
    vol.Optional(CONF_NEW_DEVICES_GROUP, default=None): cv.string,
    vol.Optional(CONF_DEVICES, default={}): vol.Schema({
        cv.string: {
            vol.Optional(CONF_NAME): cv.string,
            vol.Required(CONF_SENSOR_TYPE): cv.string,
            vol.Optional(CONF_UNIT_OF_MEASUREMENT, default=None): cv.string,
            vol.Optional(CONF_ALIASSES, default=[]):
                vol.All(cv.ensure_list, [cv.string]),
        },
    }),
})


def lookup_unit_for_sensor_type(sensor_type):
    """Get unit for sensor type.

    Async friendly.
    """
    from rflink.parser import UNITS, PACKET_FIELDS
    field_abbrev = {v: k for k, v in PACKET_FIELDS.items()}

    return UNITS.get(field_abbrev.get(sensor_type))


def devices_from_config(domain_config, hass=None):
    """Parse configuration and add Rflink sensor devices."""
    devices = []
    for device_id, config in domain_config[CONF_DEVICES].items():
        if not config[ATTR_UNIT_OF_MEASUREMENT]:
            config[ATTR_UNIT_OF_MEASUREMENT] = lookup_unit_for_sensor_type(
                config[CONF_SENSOR_TYPE])
        device = RflinkSensor(device_id, hass, **config)
        devices.append(device)

        # Register entity to listen to incoming rflink events
        hass.data[DATA_ENTITY_LOOKUP][
            EVENT_KEY_SENSOR][device_id].append(device)
    return devices


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Rflink platform."""
    async_add_devices(devices_from_config(config, hass))

    # Add new (unconfigured) devices to user desired group
    if config[CONF_NEW_DEVICES_GROUP]:
        new_devices_group = yield from group.Group.async_create_group(
            hass, config[CONF_NEW_DEVICES_GROUP], [], True)
    else:
        new_devices_group = None

    @asyncio.coroutine
    def add_new_device(event):
        """Check if device is known, otherwise create device entity."""
        device_id = event[EVENT_KEY_ID]

        rflinksensor = partial(RflinkSensor, device_id, hass)
        device = rflinksensor(event[EVENT_KEY_SENSOR], event[EVENT_KEY_UNIT])
        # Add device entity
        async_add_devices([device])

        # Register entity to listen to incoming rflink events
        hass.data[DATA_ENTITY_LOOKUP][
            EVENT_KEY_SENSOR][device_id].append(device)

        # Make sure the event is processed by the new entity
        device.handle_event(event)

        # Maybe add to new devices group
        if new_devices_group:
            yield from new_devices_group.async_update_tracked_entity_ids(
                list(new_devices_group.tracking) + [device.entity_id])

    hass.data[DATA_DEVICE_REGISTER][EVENT_KEY_SENSOR] = add_new_device


class RflinkSensor(RflinkDevice):
    """Representation of a Rflink sensor."""

    def __init__(self, device_id, hass, sensor_type, unit_of_measurement,
                 **kwargs):
        """Handle sensor specific args and super init."""
        self._sensor_type = sensor_type
        self._unit_of_measurement = unit_of_measurement
        super().__init__(device_id, hass, **kwargs)

    def _handle_event(self, event):
        """Domain specific event handler."""
        self._state = event['value']

    @property
    def entity_id(self):
        """Return entity id."""
        return "sensor.{}".format(self.name)

    @property
    def unit_of_measurement(self):
        """Return measurement unit."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return value."""
        return self._state

    @property
    def icon(self):
        """Return possible sensor specific icon."""
        if self._sensor_type in SENSOR_ICONS:
            return SENSOR_ICONS[self._sensor_type]
