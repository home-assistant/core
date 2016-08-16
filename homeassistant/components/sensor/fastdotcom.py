"""
Support for Fast.com internet speed testing sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.fastdotcom/
"""
import logging

import homeassistant.util.dt as dt_util
from homeassistant.components import recorder
from homeassistant.components.sensor import DOMAIN
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_time_change

REQUIREMENTS = ['https://github.com/nkgilley/fast.com/archive/'
                'master.zip#fastdotcom==0.0.1']

_LOGGER = logging.getLogger(__name__)

CONF_SECOND = 'second'
CONF_MINUTE = 'minute'
CONF_HOUR = 'hour'
CONF_DAY = 'day'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Fast.com sensor."""
    data = SpeedtestData(hass, config)
    sensor = SpeedtestSensor(data)
    add_devices([sensor])

    def update(call=None):
        """Update service for manual updates."""
        data.update(dt_util.now())
        sensor.update()

    hass.services.register(DOMAIN, 'update_fastdotcom', update)


# pylint: disable=too-few-public-methods
class SpeedtestSensor(Entity):
    """Implementation of a FAst.com sensor."""

    def __init__(self, speedtest_data):
        """Initialize the sensor."""
        self._name = 'Fast.com Speedtest'
        self.speedtest_client = speedtest_data
        self._state = None
        self._unit_of_measurement = 'Mbps'

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest data and update the states."""
        data = self.speedtest_client.data
        if data is None:
            entity_id = 'sensor.fastcom_speedtest'
            states = recorder.get_model('States')
            try:
                last_state = recorder.execute(
                    recorder.query('States').filter(
                        (states.entity_id == entity_id) &
                        (states.last_changed == states.last_updated) &
                        (states.state != 'unknown')
                    ).order_by(states.state_id.desc()).limit(1))
            except TypeError:
                return
            except RuntimeError:
                return
            if not last_state:
                return
            self._state = last_state[0].state
        else:
            self._state = data['download']


class SpeedtestData(object):
    """Get the latest data from fast.com."""

    def __init__(self, hass, config):
        """Initialize the data object."""
        self.data = None
        track_time_change(hass, self.update,
                          second=config.get(CONF_SECOND, 0),
                          minute=config.get(CONF_MINUTE, 0),
                          hour=config.get(CONF_HOUR, None),
                          day=config.get(CONF_DAY, None))

    def update(self, now):
        """Get the latest data from fast.com."""
        from fastdotcom import fast_com
        _LOGGER.info('Executing fast.com speedtest')
        self.data = {'download': fast_com()}
