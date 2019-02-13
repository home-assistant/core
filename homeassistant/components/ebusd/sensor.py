"""Support for Ebusd sensors."""
import logging
import datetime

from homeassistant.helpers.entity import Entity

from .const import DOMAIN

DEPENDENCIES = ['ebusd']

TIME_FRAME1_BEGIN = 'time_frame1_begin'
TIME_FRAME1_END = 'time_frame1_end'
TIME_FRAME2_BEGIN = 'time_frame2_begin'
TIME_FRAME2_END = 'time_frame2_end'
TIME_FRAME3_BEGIN = 'time_frame3_begin'
TIME_FRAME3_END = 'time_frame3_end'

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Ebus sensor."""
    ebusd_api = hass.data[DOMAIN]
    monitored_conditions = discovery_info['monitored_conditions']
    name = discovery_info['client_name']

    dev = []
    for condition in monitored_conditions:
        dev.append(EbusdSensor(
            ebusd_api, discovery_info['sensor_types'][condition], name))

    add_entities(dev, True)


class EbusdSensor(Entity):
    """Ebusd component sensor methods definition."""

    def __init__(self, data, sensor, name):
        """Initialize the sensor."""
        self._state = None
        self._client_name = name
        self._name, self._unit_of_measurement, self._icon, self._type = sensor
        self.data = data

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self._client_name, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        if self._type == 1 and self._state is not None:
            schedule = {
                TIME_FRAME1_BEGIN: None,
                TIME_FRAME1_END: None,
                TIME_FRAME2_BEGIN: None,
                TIME_FRAME2_END: None,
                TIME_FRAME3_BEGIN: None,
                TIME_FRAME3_END: None
            }
            time_frame = self._state.split(';')
            for index, item in enumerate(sorted(schedule.items())):
                if index < len(time_frame):
                    parsed = datetime.datetime.strptime(
                        time_frame[index], '%H:%M')
                    parsed = parsed.replace(
                        datetime.datetime.now().year,
                        datetime.datetime.now().month,
                        datetime.datetime.now().day)
                    schedule[item[0]] = parsed.isoformat()
            return schedule
        return None

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    def update(self):
        """Fetch new state data for the sensor."""
        try:
            self.data.update(self._name, self._type)
            if self._name not in self.data.value:
                return

            self._state = self.data.value[self._name]
        except RuntimeError:
            _LOGGER.debug("EbusdData.update exception")
