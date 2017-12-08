"""The test for the Trend sensor platform."""
from homeassistant import setup

from tests.common import get_test_home_assistant, assert_setup_component


class TestTrendBinarySensor:
    """Test the Trend sensor."""

    hass = None

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_up(self):
        """Test up trend."""
        assert setup.setup_component(self.hass, 'binary_sensor', {
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

    def test_up_using_trendline(self):
        """Test up trend using multiple samples and trendline calculation."""
        assert setup.setup_component(self.hass, 'binary_sensor', {
            'binary_sensor': {
                'platform': 'trend',
                'sensors': {
                    'test_trend_sensor': {
                        'entity_id': "sensor.test_state",
                        'sample_duration': 300,
                        'min_gradient': 1,
                        'max_samples': 25,
                    }
                }
            }
        })

        for val in [1, 0, 2, 3]:
            self.hass.states.set('sensor.test_state', val)
            self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test_trend_sensor')
        assert state.state == 'on'

        for val in [0, 1, 0, 0]:
            self.hass.states.set('sensor.test_state', val)
            self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test_trend_sensor')
        assert state.state == 'off'

    def test_down_using_trendline(self):
        """Test down trend using multiple samples and trendline calculation."""
        assert setup.setup_component(self.hass, 'binary_sensor', {
            'binary_sensor': {
                'platform': 'trend',
                'sensors': {
                    'test_trend_sensor': {
                        'entity_id': "sensor.test_state",
                        'sample_duration': 300,
                        'min_gradient': 1,
                        'max_samples': 25,
                        'invert': 'Yes'
                    }
                }
            }
        })

        for val in [3, 2, 3, 1]:
            self.hass.states.set('sensor.test_state', val)
            self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test_trend_sensor')
        assert state.state == 'on'

        for val in [4, 2, 4, 4]:
            self.hass.states.set('sensor.test_state', val)
            self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test_trend_sensor')
        assert state.state == 'off'

    def test_down(self):
        """Test down trend."""
        assert setup.setup_component(self.hass, 'binary_sensor', {
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

    def test_invert_up(self):
        """Test up trend with custom message."""
        assert setup.setup_component(self.hass, 'binary_sensor', {
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
        assert setup.setup_component(self.hass, 'binary_sensor', {
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
        assert setup.setup_component(self.hass, 'binary_sensor', {
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
        assert setup.setup_component(self.hass, 'binary_sensor', {
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

    def test_max_samples(self):
        """Test that sample count is limited correctly."""
        assert setup.setup_component(self.hass, 'binary_sensor', {
            'binary_sensor': {
                'platform': 'trend',
                'sensors': {
                    'test_trend_sensor': {
                        'entity_id': "sensor.test_state",
                        'max_samples': 3,
                        'min_gradient': -1,
                    }
                }
            }
        })

        for val in [0, 1, 2, 3, 2, 1]:
            self.hass.states.set('sensor.test_state', val)
            self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test_trend_sensor')
        assert state.state == 'on'
        assert state.attributes['sample_count'] == 3

    def test_non_numeric(self):
        """Test up trend."""
        assert setup.setup_component(self.hass, 'binary_sensor', {
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
        assert setup.setup_component(self.hass, 'binary_sensor', {
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

    def test_invalid_name_does_not_create(self): \
            # pylint: disable=invalid-name
        """Test invalid name."""
        with assert_setup_component(0):
            assert setup.setup_component(self.hass, 'binary_sensor', {
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

    def test_invalid_sensor_does_not_create(self): \
            # pylint: disable=invalid-name
        """Test invalid sensor."""
        with assert_setup_component(0):
            assert setup.setup_component(self.hass, 'binary_sensor', {
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
        with assert_setup_component(0):
            assert setup.setup_component(self.hass, 'binary_sensor', {
                'binary_sensor': {
                    'platform': 'trend'
                }
            })
        assert self.hass.states.all() == []
