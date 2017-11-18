"""The test for the Dewpoint sensor platform."""
from homeassistant.setup import setup_component
from homeassistant.const import TEMP_FAHRENHEIT
from homeassistant.util.unit_system import METRIC_SYSTEM, IMPERIAL_SYSTEM

from tests.common import get_test_home_assistant, assert_setup_component


class TestDewpointSensor:
    """Test the Dewpoint sensor."""

    hass = None
    # pylint: disable=invalid-name

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_dewpoint(self):
        """Test dewpoint."""
        with assert_setup_component(1):
            assert setup_component(self.hass, 'sensor', {
                'sensor': {
                    'platform': 'dewpoint',
                    'temperature_template': '{{ states.sensor.'
                                            'test_temperature.state }}',
                    'humidity_template': '{{ states.sensor.'
                                         'test_humidity.state }}'
                }
            })

        self.hass.config.units = METRIC_SYSTEM
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('sensor.dewpoint')
        assert state.state == 'unknown'

        self.hass.states.set('sensor.test_temperature', 20)
        self.hass.states.set('sensor.test_humidity', 58)

        self.hass.block_till_done()
        state = self.hass.states.get('sensor.dewpoint')
        assert state.state == '11.5'

    def test_dewpoint_fahrenheit(self):
        """Test dewpoint with Fahrenheit units."""
        with assert_setup_component(1):
            assert setup_component(self.hass, 'sensor', {
                'sensor': {
                    'platform': 'dewpoint',
                    'temperature_template': '{{ states.sensor.'
                                            'test_temperature.state }}',
                    'humidity_template': '{{ states.sensor.'
                                         'test_humidity.state }}',
                    'unit_of_measurement': TEMP_FAHRENHEIT,
                }
            })

        self.hass.config.units = IMPERIAL_SYSTEM
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('sensor.dewpoint')
        assert state.state == 'unknown'

        self.hass.states.set('sensor.test_temperature', 68)
        self.hass.states.set('sensor.test_humidity', 58)

        self.hass.block_till_done()
        state = self.hass.states.get('sensor.dewpoint')
        assert state.state == '52.7'

    def test_dewpoint_template_syntax_error(self):
        """Test templating syntax error."""
        with assert_setup_component(0):
            assert setup_component(self.hass, 'sensor', {
                'sensor': {
                    'platform': 'dewpoint',
                    'temperature_template': "{% if rubbish %}",
                    'humidity_template': "{% if rubbish %}"
                }
            })

        self.hass.start()
        self.hass.block_till_done()
        assert self.hass.states.all() == []

    def test_dewpoint_invalid_config_does_not_create(self):
        """Test missing required config element."""
        with assert_setup_component(0):
            assert setup_component(self.hass, 'sensor', {
                'sensor': {
                    'platform': 'dewpoint',
                    'humidity_template': '{{ states.sensor.'
                                         'test_humidity.state }}'
                }
            })

        self.hass.start()

        assert self.hass.states.all() == []

    def test_dewpoint_state_missing(self):
        """Test missing attribute dewpoint."""
        with assert_setup_component(1):
            assert setup_component(self.hass, 'sensor', {
                'sensor': {
                    'platform': 'dewpoint',
                    'temperature_template': '{{ states.sensor.'
                                            'test_temperature.state }}',
                    'humidity_template': '{{ states.sensor.'
                                         'test_humidity.state }}'
                }
            })

        self.hass.start()
        self.hass.block_till_done()
        state = self.hass.states.get('sensor.dewpoint')
        assert state.state == 'unknown'
