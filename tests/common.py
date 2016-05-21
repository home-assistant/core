"""Test the helper method for writing tests."""
import os
from datetime import timedelta
from unittest import mock

from homeassistant import core as ha, loader
from homeassistant.bootstrap import _setup_component
from homeassistant.helpers.entity import ToggleEntity
import homeassistant.util.dt as date_util
from homeassistant.const import (
    STATE_ON, STATE_OFF, DEVICE_DEFAULT_NAME, EVENT_TIME_CHANGED,
    EVENT_STATE_CHANGED, EVENT_PLATFORM_DISCOVERED, ATTR_SERVICE,
    ATTR_DISCOVERED, SERVER_PORT, TEMP_CELSIUS)
from homeassistant.components import sun, mqtt

_TEST_INSTANCE_PORT = SERVER_PORT


def get_test_config_dir():
    """Return a path to a test config dir."""
    return os.path.join(os.path.dirname(__file__), "config")


def get_test_home_assistant(num_threads=None):
    """Return a Home Assistant object pointing at test config dir."""
    if num_threads:
        orig_num_threads = ha.MIN_WORKER_THREAD
        ha.MIN_WORKER_THREAD = num_threads

    hass = ha.HomeAssistant()

    if num_threads:
        ha.MIN_WORKER_THREAD = orig_num_threads

    hass.config.config_dir = get_test_config_dir()
    hass.config.latitude = 32.87336
    hass.config.longitude = -117.22743
    hass.config.time_zone = date_util.get_time_zone('US/Pacific')
    hass.config.temperature_unit = TEMP_CELSIUS

    if 'custom_components.test' not in loader.AVAILABLE_COMPONENTS:
        loader.prepare(hass)

    return hass


def get_test_instance_port():
    """Return unused port for running test instance.

    The socket that holds the default port does not get released when we stop
    HA in a different test case. Until I have figured out what is going on,
    let's run each test on a different port.
    """
    global _TEST_INSTANCE_PORT
    _TEST_INSTANCE_PORT += 1
    return _TEST_INSTANCE_PORT


def mock_service(hass, domain, service):
    """Setup a fake service.

    Return a list that logs all calls to fake service.
    """
    calls = []

    hass.services.register(
        domain, service, lambda call: calls.append(call))

    return calls


def fire_mqtt_message(hass, topic, payload, qos=0):
    """Fire the MQTT message."""
    hass.bus.fire(mqtt.EVENT_MQTT_MESSAGE_RECEIVED, {
        mqtt.ATTR_TOPIC: topic,
        mqtt.ATTR_PAYLOAD: payload,
        mqtt.ATTR_QOS: qos,
    })


def fire_time_changed(hass, time):
    """Fire a time changes event."""
    hass.bus.fire(EVENT_TIME_CHANGED, {'now': time})


def fire_service_discovered(hass, service, info):
    """Fire the MQTT message."""
    hass.bus.fire(EVENT_PLATFORM_DISCOVERED, {
        ATTR_SERVICE: service,
        ATTR_DISCOVERED: info
    })


def ensure_sun_risen(hass):
    """Trigger sun to rise if below horizon."""
    if sun.is_on(hass):
        return
    fire_time_changed(hass, sun.next_rising_utc(hass) + timedelta(seconds=10))


def ensure_sun_set(hass):
    """Trigger sun to set if above horizon."""
    if not sun.is_on(hass):
        return
    fire_time_changed(hass, sun.next_setting_utc(hass) + timedelta(seconds=10))


def mock_state_change_event(hass, new_state, old_state=None):
    """Mock state change envent."""
    event_data = {
        'entity_id': new_state.entity_id,
        'new_state': new_state,
    }

    if old_state:
        event_data['old_state'] = old_state

    hass.bus.fire(EVENT_STATE_CHANGED, event_data)


def mock_http_component(hass):
    """Mock the HTTP component."""
    hass.wsgi = mock.MagicMock()
    hass.config.components.append('http')


@mock.patch('homeassistant.components.mqtt.MQTT')
def mock_mqtt_component(hass, mock_mqtt):
    """Mock the MQTT component."""
    _setup_component(hass, mqtt.DOMAIN, {
        mqtt.DOMAIN: {
            mqtt.CONF_BROKER: 'mock-broker',
        }
    })
    return mock_mqtt


class MockModule(object):
    """Representation of a fake module."""

    def __init__(self, domain=None, dependencies=None, setup=None,
                 requirements=None, config_schema=None, platform_schema=None):
        """Initialize the mock module."""
        self.DOMAIN = domain
        self.DEPENDENCIES = dependencies or []
        self.REQUIREMENTS = requirements or []

        if config_schema is not None:
            self.CONFIG_SCHEMA = config_schema

        if platform_schema is not None:
            self.PLATFORM_SCHEMA = platform_schema

        # Setup a mock setup if none given.
        if setup is None:
            self.setup = lambda hass, config: True
        else:
            self.setup = setup


class MockPlatform(object):
    """Provide a fake platform."""

    def __init__(self, setup_platform=None, dependencies=None,
                 platform_schema=None):
        """Initialize the platform."""
        self.DEPENDENCIES = dependencies or []
        self._setup_platform = setup_platform

        if platform_schema is not None:
            self.PLATFORM_SCHEMA = platform_schema

    def setup_platform(self, hass, config, add_devices, discovery_info=None):
        """Setup the platform."""
        if self._setup_platform is not None:
            self._setup_platform(hass, config, add_devices, discovery_info)


class MockToggleDevice(ToggleEntity):
    """Provide a mock toggle device."""

    def __init__(self, name, state):
        """Initialize the mock device."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._state = state
        self.calls = []

    @property
    def name(self):
        """Return the name of the device if any."""
        self.calls.append(('name', {}))
        return self._name

    @property
    def state(self):
        """Return the name of the device if any."""
        self.calls.append(('state', {}))
        return self._state

    @property
    def is_on(self):
        """Return true if device is on."""
        self.calls.append(('is_on', {}))
        return self._state == STATE_ON

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self.calls.append(('turn_on', kwargs))
        self._state = STATE_ON

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self.calls.append(('turn_off', kwargs))
        self._state = STATE_OFF

    def last_call(self, method=None):
        """Return the last call."""
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
