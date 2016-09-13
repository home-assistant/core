"""The test for the Trend sensor platform."""
import homeassistant.bootstrap as bootstrap

from tests.common import get_test_home_assistant


class TestTrendBinarySensor:
    """Test the Trend sensor."""

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_up(self):
        """Test up trend."""
        assert bootstrap.setup_component(self.hass, 'binary_sensor', {
            'binary_sensor': {
                'platform': 'trend',
                'sensors': {
                    'test_trend_sensor': {
                        'entity_id':
                            "sensor.test_state"
                    }
                }
            }
        })

        self.hass.states.set('sensor.test_state', '1')
        self.hass.block_till_done()
        self.hass.states.set('sensor.test_state', '2')
        self.hass.block_till_done()
        state = self.hass.states.get('binary_sensor.test_trend_sensor')
        assert state.state == 'on'

    def test_down(self):
        """Test down trend."""
        assert bootstrap.setup_component(self.hass, 'binary_sensor', {
            'binary_sensor': {
                'platform': 'trend',
                'sensors': {
                    'test_trend_sensor': {
                        'entity_id':
                            "sensor.test_state"
                    }
                }
            }
        })

        self.hass.states.set('sensor.test_state', '2')
        self.hass.block_till_done()
        self.hass.states.set('sensor.test_state', '1')
        self.hass.block_till_done()
        state = self.hass.states.get('binary_sensor.test_trend_sensor')
        assert state.state == 'off'

    def test__invert_up(self):
        """Test up trend with custom message."""
        assert bootstrap.setup_component(self.hass, 'binary_sensor', {
            'binary_sensor': {
                'platform': 'trend',
                'sensors': {
                    'test_trend_sensor': {
                        'entity_id':
                            "sensor.test_state",
                        'invert': "Yes"
                    }
                }
            }
        })

        self.hass.states.set('sensor.test_state', '1')
        self.hass.block_till_done()
        self.hass.states.set('sensor.test_state', '2')
        self.hass.block_till_done()
        state = self.hass.states.get('binary_sensor.test_trend_sensor')
        assert state.state == 'off'

    def test_invert_down(self):
        """Test down trend with custom message."""
        assert bootstrap.setup_component(self.hass, 'binary_sensor', {
            'binary_sensor': {
                'platform': 'trend',
                'sensors': {
                    'test_trend_sensor': {
                        'entity_id':
                            "sensor.test_state",
                        'invert': "Yes"
                    }
                }
            }
        })

        self.hass.states.set('sensor.test_state', '2')
        self.hass.block_till_done()
        self.hass.states.set('sensor.test_state', '1')
        self.hass.block_till_done()
        state = self.hass.states.get('binary_sensor.test_trend_sensor')
        assert state.state == 'on'

    def test_attribute_up(self):
        """Test attribute up trend."""
        assert bootstrap.setup_component(self.hass, 'binary_sensor', {
            'binary_sensor': {
                'platform': 'trend',
                'sensors': {
                    'test_trend_sensor': {
                        'entity_id':
                            "sensor.test_state",
                        'attribute': 'attr'
                    }
                }
            }
        })
        self.hass.states.set('sensor.test_state', 'State', {'attr': '1'})
        self.hass.block_till_done()
        self.hass.states.set('sensor.test_state', 'State', {'attr': '2'})
        self.hass.block_till_done()
        state = self.hass.states.get('binary_sensor.test_trend_sensor')
        assert state.state == 'on'

    def test_attribute_down(self):
        """Test attribute down trend."""
        assert bootstrap.setup_component(self.hass, 'binary_sensor', {
            'binary_sensor': {
                'platform': 'trend',
                'sensors': {
                    'test_trend_sensor': {
                        'entity_id':
                            "sensor.test_state",
                        'attribute': 'attr'
                    }
                }
            }
        })

        self.hass.states.set('sensor.test_state', 'State', {'attr': '2'})
        self.hass.block_till_done()
        self.hass.states.set('sensor.test_state', 'State', {'attr': '1'})

        self.hass.block_till_done()
        state = self.hass.states.get('binary_sensor.test_trend_sensor')
        assert state.state == 'off'

    def test_non_numeric(self):
        """Test up trend."""
        assert bootstrap.setup_component(self.hass, 'binary_sensor', {
            'binary_sensor': {
                'platform': 'trend',
                'sensors': {
                    'test_trend_sensor': {
                        'entity_id':
                            "sensor.test_state"
                    }
                }
            }
        })

        self.hass.states.set('sensor.test_state', 'Non')
        self.hass.block_till_done()
        self.hass.states.set('sensor.test_state', 'Numeric')
        self.hass.block_till_done()
        state = self.hass.states.get('binary_sensor.test_trend_sensor')
        assert state.state == 'off'

    def test_missing_attribute(self):
        """Test attribute down trend."""
        assert bootstrap.setup_component(self.hass, 'binary_sensor', {
            'binary_sensor': {
                'platform': 'trend',
                'sensors': {
                    'test_trend_sensor': {
                        'entity_id':
                            "sensor.test_state",
                        'attribute': 'missing'
                    }
                }
            }
        })

        self.hass.states.set('sensor.test_state', 'State', {'attr': '2'})
        self.hass.block_till_done()
        self.hass.states.set('sensor.test_state', 'State', {'attr': '1'})

        self.hass.block_till_done()
        state = self.hass.states.get('binary_sensor.test_trend_sensor')
        assert state.state == 'off'

    def test_invalid_name_does_not_create(self):
        """Test invalid name."""
        assert not bootstrap.setup_component(self.hass, 'binary_sensor', {
            'binary_sensor': {
                'platform': 'template',
                'sensors': {
                    'test INVALID sensor': {
                        'entity_id':
                            "sensor.test_state"
                    }
                }
            }
        })
        assert self.hass.states.all() == []

    def test_invalid_sensor_does_not_create(self):
        """Test invalid sensor."""
        assert not bootstrap.setup_component(self.hass, 'binary_sensor', {
            'binary_sensor': {
                'platform': 'template',
                'sensors': {
                    'test_trend_sensor': {
                        'not_entity_id':
                            "sensor.test_state"
                    }
                }
            }
        })
        assert self.hass.states.all() == []

    def test_no_sensors_does_not_create(self):
        """Test no sensors."""
        assert not bootstrap.setup_component(self.hass, 'binary_sensor', {
            'binary_sensor': {
                'platform': 'trend'
            }
        })
        assert self.hass.states.all() == []
