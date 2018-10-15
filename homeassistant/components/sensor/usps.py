"""
Sensor for USPS packages.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.usps/
"""
from collections import defaultdict
import logging

from homeassistant.components.usps import DATA_USPS
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_DATE
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify
from homeassistant.util.dt import now

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['usps']

STATUS_DELIVERED = 'delivered'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the USPS platform."""
    if discovery_info is None:
        return

    usps = hass.data[DATA_USPS]
    add_entities([USPSPackageSensor(usps), USPSMailSensor(usps)], True)


class USPSPackageSensor(Entity):
    """USPS Package Sensor."""

    def __init__(self, usps):
        """Initialize the sensor."""
        self._usps = usps
        self._name = self._usps.name
        self._attributes = None
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} packages'.format(self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Update device state."""
        self._usps.update()
        status_counts = defaultdict(int)
        for package in self._usps.packages:
            status = slugify(package['primary_status'])
            if status == STATUS_DELIVERED and \
                    package['delivery_date'] < now().date():
                continue
            status_counts[status] += 1
        self._attributes = {
            ATTR_ATTRIBUTION: self._usps.attribution
        }
        self._attributes.update(status_counts)
        self._state = sum(status_counts.values())

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return 'mdi:package-variant-closed'

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return 'packages'


class USPSMailSensor(Entity):
    """USPS Mail Sensor."""

    def __init__(self, usps):
        """Initialize the sensor."""
        self._usps = usps
        self._name = self._usps.name
        self._attributes = None
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} mail'.format(self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Update device state."""
        self._usps.update()
        if self._usps.mail is not None:
            self._state = len(self._usps.mail)
        else:
            self._state = 0

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = {}
        attr[ATTR_ATTRIBUTION] = self._usps.attribution
        try:
            attr[ATTR_DATE] = str(self._usps.mail[0]['date'])
        except IndexError:
            pass
        return attr

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return 'mdi:mailbox'

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return 'pieces'
