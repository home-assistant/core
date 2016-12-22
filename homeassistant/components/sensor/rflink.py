"""Support for Rflink lights.

For more details about this platform, please refer to the documentation
at https://home-assistant.io/components/light.rflink/

"""
import asyncio
from functools import partial
import logging

from homeassistant.components import group
import homeassistant.components.rflink as rflink

from . import DOMAIN

DEPENDENCIES = ['rflink']

_LOGGER = logging.getLogger(__name__)

SENSOR_ICONS = {
    'humidity': 'mdi:water-percent',
    'battery': 'mdi:battery',
    'temperature': 'mdi:thermometer',
}

VALID_CONFIG_KEYS = [
    'aliasses',
    'name',
    'icon',
    'sensor_type',
]


def lookup_unit_for_sensor_type(sensor_type):
    """Get unit for sensor type."""
    from rflink.parser import UNITS, PACKET_FIELDS
    field_abbrev = {v: k for k, v in PACKET_FIELDS.items()}

    return UNITS.get(field_abbrev.get(sensor_type))


def devices_from_config(domain_config, hass=None):
    """Parse config and add rflink sensor devices."""
    devices = []
    for device_id, config in domain_config.get('devices', {}).items():
        # extract only valid keys from device configuration
        kwargs = {k: v for k, v in config.items() if k in VALID_CONFIG_KEYS}
        kwargs['unit'] = lookup_unit_for_sensor_type(kwargs['sensor_type'])
        devices.append(RflinkSensor(device_id, hass, **kwargs))
        rflink.KNOWN_DEVICE_IDS.append(device_id)
    return devices


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup the Rflink platform."""
    # add devices from config
    yield from async_add_devices(devices_from_config(config, hass))

    # add new (unconfigured) devices to user desired group
    if config.get('new_devices_group'):
        new_devices_group = yield from group.Group.async_create_group(
            hass, config.get('new_devices_group'), [], True)
    else:
        new_devices_group = None

    @asyncio.coroutine
    def add_new_device(event):
        """Check if device is known, otherwise create device entity."""
        event = event.data[rflink.ATTR_EVENT]
        device_id = event['id']
        if device_id not in rflink.KNOWN_DEVICE_IDS:
            rflink.KNOWN_DEVICE_IDS.append(device_id)
            rflinksensor = partial(RflinkSensor, device_id, hass)
            device = rflinksensor(event['sensor'], event['unit'])
            # add device entity
            yield from async_add_devices([device])
            # make sure the event is processed by the new entity
            device.match_event(event)

            # maybe add to new devices group
            if new_devices_group:
                yield from new_devices_group.async_update_tracked_entity_ids(
                    list(new_devices_group.tracking) + [device.entity_id])

    hass.bus.async_listen(rflink.RFLINK_EVENT[DOMAIN], add_new_device)


class RflinkSensor(rflink.RflinkDevice):
    """Representation of a Rflink sensor."""

    # used for matching bus events
    domain = DOMAIN

    def __init__(self, device_id, hass, sensor_type, unit, **kwargs):
        """Handle sensor specific args and super init."""
        self._sensor_type = sensor_type
        self._unit = unit
        super().__init__(device_id, hass, **kwargs)

    def _handle_event(self, event):
        """Domain specific event handler."""
        self._state = event['value']

    @property
    def unit_of_measurement(self):
        """Return measurement unit."""
        return self._unit

    @property
    def state(self):
        """Return value."""
        return self._state

    @property
    def icon(self):
        """Return possible sensor specific icon or user override."""
        if self._icon:
            return self._icon
        elif self._sensor_type in SENSOR_ICONS:
            return SENSOR_ICONS[self._sensor_type]
