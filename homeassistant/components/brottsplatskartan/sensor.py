"""Sensor platform for Brottsplatskartan information."""
from collections import defaultdict

from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import ATTR_INCIDENTS, ATTR_TITLE_TYPE, DOMAIN, SIGNAL_UPDATE_BPK


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Brottsplatskartan platform."""
    attribution = hass.data[DOMAIN][ATTR_ATTRIBUTION]
    bpk = hass.data[DOMAIN]
    name = hass.data[DOMAIN][CONF_NAME]
    incidents = hass.data[DOMAIN][ATTR_INCIDENTS]
    add_entities([BrottsplatskartanSensor(attribution, bpk, incidents, name)],
                 True)


class BrottsplatskartanSensor(Entity):
    """Representation of a Brottsplatskartan Sensor."""

    def __init__(self, attribution, bpk, incidents, name):
        """Initialize the Brottsplatskartan sensor."""
        self._attribution = attribution
        self._attributes = {}
        self._brottsplatskartan = bpk
        self._incidents = incidents
        self._name = name
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    async def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(self.hass, SIGNAL_UPDATE_BPK,
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
