"""Support for Minut Point."""
import logging

from homeassistant.components.alarm_control_panel import (DOMAIN,
                                                          AlarmControlPanel)
from homeassistant.const import (STATE_ALARM_ARMED_AWAY, STATE_ALARM_DISARMED)
from homeassistant.components.point.const import (
    DOMAIN as POINT_DOMAIN, POINT_DISCOVERY_NEW)
from homeassistant.helpers.dispatcher import async_dispatcher_connect

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a Point's alarm_control_panel based on a config entry."""
    async def async_discover_home(home_id):
        """Discover and add a discovered home."""
        client = hass.data[POINT_DOMAIN][config_entry.entry_id]
        async_add_entities([MinutPointAlarmControl(client, home_id)], True)

    async_dispatcher_connect(
        hass, POINT_DISCOVERY_NEW.format(DOMAIN, POINT_DOMAIN),
        async_discover_home)


class MinutPointAlarmControl(AlarmControlPanel):
    """The platform class required by Home Assistant."""

    def __init__(self, point_client, home_id):
        """Initialize the entity."""
        self._client = point_client
        self._home_id = home_id

    @property
    def _home(self):
        """Return the home object."""
        return self._client.homes[self._home_id]

    @property
    def name(self):
        """Return name of the device."""
        return self._home['name']

    @property
    def state(self):
        """Return state of the device."""
        return STATE_ALARM_DISARMED if self._home[
            'alarm_status'] == 'off' else STATE_ALARM_ARMED_AWAY

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        status = self._client.alarm_disarm(self._home_id)
        if status:
            self._home['alarm_status'] = 'off'

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        status = self._client.alarm_arm(self._home_id)
        if status:
            self._home['alarm_status'] = 'on'

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return 'point.{}'.format(self._home_id)

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return {
            'identifiers': {(POINT_DOMAIN, self._home_id)},
            'name': self.name,
            'manufacturer': 'Minut',
        }
