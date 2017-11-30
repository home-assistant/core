"""The tests for the MoldIndicator sensor."""
import unittest

from homeassistant.setup import setup_component
import homeassistant.components.sensor as sensor
from homeassistant.components.sensor.mold_indicator import (ATTR_DEWPOINT,
                                                            ATTR_CRITICAL_TEMP)
from homeassistant.const import (ATTR_UNIT_OF_MEASUREMENT,
                                 TEMP_CELSIUS)

from tests.common import get_test_home_assistant


class TestSensorMoldIndicator(unittest.TestCase):
    """Test the MoldIndicator sensor."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.states.set('test.indoortemp', '20',
                             {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.states.set('test.outdoortemp', '10',
                             {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.states.set('test.indoorhumidity', '50',
                             {ATTR_UNIT_OF_MEASUREMENT: '%'})

    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    def test_setup(self):
        """Test the mold indicator sensor setup."""
        self.assertTrue(setup_component(self.hass, sensor.DOMAIN, {
            'sensor': {
                'platform': 'mold_indicator',
                'indoor_temp_sensor': 'test.indoortemp',
                'outdoor_temp_sensor': 'test.outdoortemp',
                'indoor_humidity_sensor': 'test.indoorhumidity',
                'calibration_factor': 2.0
            }
        }))

        moldind = self.hass.states.get('sensor.mold_indicator')
        assert moldind
        assert '%' == moldind.attributes.get('unit_of_measurement')

    def test_invalidhum(self):
        """Test invalid sensor values."""
        self.hass.states.set('test.indoortemp', '10',
                             {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.states.set('test.outdoortemp', '10',
                             {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.states.set('test.indoorhumidity', '0',
                             {ATTR_UNIT_OF_MEASUREMENT: '%'})

        self.assertTrue(setup_component(self.hass, sensor.DOMAIN, {
            'sensor': {
                'platform': 'mold_indicator',
                'indoor_temp_sensor': 'test.indoortemp',
                'outdoor_temp_sensor': 'test.outdoortemp',
                'indoor_humidity_sensor': 'test.indoorhumidity',
                'calibration_factor': 2.0
            }
        }))
        moldind = self.hass.states.get('sensor.mold_indicator')
        assert moldind
        assert moldind.state == '0'

    def test_calculation(self):
        """Test the mold indicator internal calculations."""
        self.assertTrue(setup_component(self.hass, sensor.DOMAIN, {
            'sensor': {
                'platform': 'mold_indicator',
                'indoor_temp_sensor': 'test.indoortemp',
                'outdoor_temp_sensor': 'test.outdoortemp',
                'indoor_humidity_sensor': 'test.indoorhumidity',
                'calibration_factor': 2.0
            }
        }))

        moldind = self.hass.states.get('sensor.mold_indicator')
        assert moldind

        # assert dewpoint
        dewpoint = moldind.attributes.get(ATTR_DEWPOINT)
        assert dewpoint
        assert dewpoint > 9.25
        assert dewpoint < 9.26

        # assert temperature estimation
        esttemp = moldind.attributes.get(ATTR_CRITICAL_TEMP)
        assert esttemp
        assert esttemp > 14.9
        assert esttemp < 15.1

        # assert mold indicator value
        state = moldind.state
        assert state
        assert state == '68'

    def test_sensor_changed(self):
        """Test the sensor_changed function."""
        self.assertTrue(setup_component(self.hass, sensor.DOMAIN, {
            'sensor': {
                'platform': 'mold_indicator',
                'indoor_temp_sensor': 'test.indoortemp',
                'outdoor_temp_sensor': 'test.outdoortemp',
                'indoor_humidity_sensor': 'test.indoorhumidity',
                'calibration_factor': 2.0
            }
        }))

        self.hass.states.set('test.indoortemp', '30',
                             {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()
        assert self.hass.states.get('sensor.mold_indicator').state == '90'

        self.hass.states.set('test.outdoortemp', '25',
                             {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()
        assert self.hass.states.get('sensor.mold_indicator').state == '57'

        self.hass.states.set('test.indoorhumidity', '20',
                             {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        self.hass.block_till_done()
        assert self.hass.states.get('sensor.mold_indicator').state == '23'
