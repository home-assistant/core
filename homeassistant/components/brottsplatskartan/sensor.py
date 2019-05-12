"""Sensor platform for Brottsplatskartan information."""
from collections import defaultdict

from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

from .const import ATTR_INCIDENTS, ATTR_TITLE_TYPE, DOMAIN, SIGNAL_UPDATE_BPK


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Brottsplatskartan platform."""
    monitored_conditions = discovery_info['monitored_conditions']
    attribution = hass.data[DOMAIN][ATTR_ATTRIBUTION]
    name = hass.data[DOMAIN][CONF_NAME]
    incidents = hass.data[DOMAIN][ATTR_INCIDENTS]

    sensors = []
    if incidents is False:
        return False
    for incident_area in incidents:
        if len(incidents) > 1:
            name = "{} {}".format(hass.data[DOMAIN][CONF_NAME], incident_area)
        for condition in monitored_conditions:
            slugify_incident_area = slugify(incident_area)
            incident_area_update_signal = "{}_{}".format(
                SIGNAL_UPDATE_BPK, slugify_incident_area)
            sensors.append(
                BrottsplatskartanSensor(attribution, incidents[incident_area],
                                        name, condition,
                                        incident_area_update_signal))
    add_entities(sensors, True)


class BrottsplatskartanSensor(Entity):
    """Representation of a Brottsplatskartan Sensor."""

    def __init__(self, attribution, incidents, name, sensor, update_signal):
        """Initialize the Brottsplatskartan sensor."""
        self._attribution = attribution
        self._attributes = {}
        self._incidents = incidents
        self._name = name
        self._state = None
        self._update_signal = update_signal

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    async def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(self.hass, self._update_signal,
                                 self._update_callback)

    def _update_callback(self):
        """Call update method."""
        self.schedule_update_ha_state(True)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def should_poll(self):
        """Return that this sensor does not poll."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    def update(self):
        """Update device state."""
        incident_counts = defaultdict(int)

        for incident in self._incidents:
            incident_type = incident.get(ATTR_TITLE_TYPE)
            incident_counts[incident_type] += 1

        self._attributes = {ATTR_ATTRIBUTION: self._attribution}
        self._attributes.update(incident_counts)
        self._state = len(self._incidents)
