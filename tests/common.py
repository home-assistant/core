"""
tests.helper
~~~~~~~~~~~~~

Helper method for writing tests.
"""
import os
from datetime import timedelta
from unittest import mock

import homeassistant.core as ha
import homeassistant.util.location as location_util
import homeassistant.util.dt as dt_util
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.const import (
    STATE_ON, STATE_OFF, DEVICE_DEFAULT_NAME, EVENT_TIME_CHANGED,
    EVENT_STATE_CHANGED)
from homeassistant.components import sun, mqtt


def get_test_config_dir():
    """ Returns a path to a test config dir. """
    return os.path.join(os.path.dirname(__file__), "config")


def get_test_home_assistant(num_threads=None):
    """ Returns a Home Assistant object pointing at test config dir. """
    if num_threads:
        orig_num_threads = ha.MIN_WORKER_THREAD
        ha.MIN_WORKER_THREAD = num_threads

    hass = ha.HomeAssistant()

    if num_threads:
        ha.MIN_WORKER_THREAD = orig_num_threads

    hass.config.config_dir = get_test_config_dir()
    hass.config.latitude = 32.87336
    hass.config.longitude = -117.22743

    return hass


def mock_detect_location_info():
    """ Mock implementation of util.detect_location_info. """
    return location_util.LocationInfo(
        ip='1.1.1.1',
        country_code='US',
        country_name='United States',
        region_code='CA',
        region_name='California',
        city='San Diego',
        zip_code='92122',
        time_zone='America/Los_Angeles',
        latitude='2.0',
        longitude='1.0',
        use_fahrenheit=True,
    )


def mock_service(hass, domain, service):
    """
    Sets up a fake service.
    Returns a list that logs all calls to fake service.
    """
    calls = []

    hass.services.register(
        domain, service, lambda call: calls.append(call))

    return calls


def fire_mqtt_message(hass, topic, payload, qos=0):
    hass.bus.fire(mqtt.EVENT_MQTT_MESSAGE_RECEIVED, {
        mqtt.ATTR_TOPIC: topic,
        mqtt.ATTR_PAYLOAD: payload,
        mqtt.ATTR_QOS: qos,
    })


def fire_time_changed(hass, time):
    hass.bus.fire(EVENT_TIME_CHANGED, {'now': time})


def trigger_device_tracker_scan(hass):
    """ Triggers the device tracker to scan. """
    fire_time_changed(
        hass, dt_util.utcnow().replace(second=0) + timedelta(hours=1))


def ensure_sun_risen(hass):
    """ Trigger sun to rise if below horizon. """
    if sun.is_on(hass):
        return
    fire_time_changed(hass, sun.next_rising_utc(hass) + timedelta(seconds=10))


def ensure_sun_set(hass):
    """ Trigger sun to set if above horizon. """
    if not sun.is_on(hass):
        return
    fire_time_changed(hass, sun.next_setting_utc(hass) + timedelta(seconds=10))


def mock_state_change_event(hass, new_state, old_state=None):
    event_data = {
        'entity_id': new_state.entity_id,
        'new_state': new_state,
    }

    if old_state:
        event_data['old_state'] = old_state

    hass.bus.fire(EVENT_STATE_CHANGED, event_data)


def mock_http_component(hass):
    hass.http = MockHTTP()
    hass.config.components.append('http')


def mock_mqtt_component(hass):
    with mock.patch('homeassistant.components.mqtt.MQTT'):
        mqtt.setup(hass, {
            mqtt.DOMAIN: {
                mqtt.CONF_BROKER: 'mock-broker',
            }
        })
        hass.config.components.append(mqtt.DOMAIN)


class MockHTTP(object):
    """ Mocks the HTTP module. """

    def register_path(self, method, url, callback, require_auth=True):
        pass


class MockModule(object):
    """ Provides a fake module. """

    def __init__(self, domain, dependencies=[], setup=None):
        self.DOMAIN = domain
        self.DEPENDENCIES = dependencies
        # Setup a mock setup if none given.
        self.setup = lambda hass, config: False if setup is None else setup


class MockToggleDevice(ToggleEntity):
    """ Provides a mock toggle device. """
    def __init__(self, name, state):
        self._name = name or DEVICE_DEFAULT_NAME
        self._state = state
        self.calls = []

    @property
    def name(self):
        """ Returns the name of the device if any. """
        self.calls.append(('name', {}))
        return self._name

    @property
    def state(self):
        """ Returns the name of the device if any. """
        self.calls.append(('state', {}))
        return self._state

    @property
    def is_on(self):
        """ True if device is on. """
        self.calls.append(('is_on', {}))
        return self._state == STATE_ON

    def turn_on(self, **kwargs):
        """ Turn the device on. """
        self.calls.append(('turn_on', kwargs))
        self._state = STATE_ON

    def turn_off(self, **kwargs):
        """ Turn the device off. """
        self.calls.append(('turn_off', kwargs))
        self._state = STATE_OFF

    def last_call(self, method=None):
        if not self.calls:
            return None
        elif method is None:
            return self.calls[-1]
        else:
            try:
                return next(call for call in reversed(self.calls)
                            if call[0] == method)
            except StopIteration:
                return None
