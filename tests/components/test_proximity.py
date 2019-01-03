"""The tests for the Proximity component."""
import unittest

from homeassistant.components import proximity
from homeassistant.components.proximity import DOMAIN

from homeassistant.setup import setup_component
from tests.common import get_test_home_assistant


class TestProximity(unittest.TestCase):
    """Test the Proximity component."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.states.set(
            'zone.home', 'zoning',
            {
                'name': 'home',
                'latitude': 2.1,
                'longitude': 1.1,
                'radius': 10
            })
        self.hass.states.set(
            'zone.work', 'zoning',
            {
                'name': 'work',
                'latitude': 2.3,
                'longitude': 1.3,
                'radius': 10
            })

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_proximities(self):
        """Test a list of proximities."""
        config = {
            'proximity': {
                'home': {
                    'ignored_zones': [
                        'work'
                    ],
                    'devices': [
                        'device_tracker.test1',
                        'device_tracker.test2'
                    ],
                    'tolerance': '1'
                },
                'work': {
                    'devices': [
                        'device_tracker.test1'
                    ],
                    'tolerance': '1'
                }
            }
        }

        assert setup_component(self.hass, DOMAIN, config)

        proximities = ['home', 'work']

        for prox in proximities:
            state = self.hass.states.get('proximity.' + prox)
            assert state.state == 'not set'
            assert state.attributes.get('nearest') == 'not set'
            assert state.attributes.get('dir_of_travel') == 'not set'

            self.hass.states.set('proximity.' + prox, '0')
            self.hass.block_till_done()
            state = self.hass.states.get('proximity.' + prox)
            assert state.state == '0'

    def test_proximities_setup(self):
        """Test a list of proximities with missing devices."""
        config = {
            'proximity': {
                'home': {
                    'ignored_zones': [
                        'work'
                    ],
                    'devices': [
                        'device_tracker.test1',
                        'device_tracker.test2'
                    ],
                    'tolerance': '1'
                },
                'work': {
                    'tolerance': '1'
                }
            }
        }

        assert setup_component(self.hass, DOMAIN, config)

    def test_proximity(self):
        """Test the proximity."""
        config = {
            'proximity': {
                'home': {
                    'ignored_zones': [
                        'work'
                    ],
                    'devices': [
                        'device_tracker.test1',
                        'device_tracker.test2'
                    ],
                    'tolerance': '1'
                }
            }
        }

        assert setup_component(self.hass, DOMAIN, config)

        state = self.hass.states.get('proximity.home')
        assert state.state == 'not set'
        assert state.attributes.get('nearest') == 'not set'
        assert state.attributes.get('dir_of_travel') == 'not set'

        self.hass.states.set('proximity.home', '0')
        self.hass.block_till_done()
        state = self.hass.states.get('proximity.home')
        assert state.state == '0'

    def test_device_tracker_test1_in_zone(self):
        """Test for tracker in zone."""
        config = {
            'proximity': {
                'home': {
                    'ignored_zones': [
                        'work'
                    ],
                    'devices': [
                        'device_tracker.test1'
                    ],
                    'tolerance': '1'
                }
            }
        }

        assert setup_component(self.hass, DOMAIN, config)

        self.hass.states.set(
            'device_tracker.test1', 'home',
            {
                'friendly_name': 'test1',
                'latitude': 2.1,
                'longitude': 1.1
            })
        self.hass.block_till_done()
        state = self.hass.states.get('proximity.home')
        assert state.state == '0'
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'arrived'

    def test_device_trackers_in_zone(self):
        """Test for trackers in zone."""
        config = {
            'proximity': {
                'home': {
                    'ignored_zones': [
                        'work'
                    ],
                    'devices': [
                        'device_tracker.test1',
                        'device_tracker.test2'
                    ],
                    'tolerance': '1'
                }
            }
        }

        assert setup_component(self.hass, DOMAIN, config)

        self.hass.states.set(
            'device_tracker.test1', 'home',
            {
                'friendly_name': 'test1',
                'latitude': 2.1,
                'longitude': 1.1
            })
        self.hass.block_till_done()
        self.hass.states.set(
            'device_tracker.test2', 'home',
            {
                'friendly_name': 'test2',
                'latitude': 2.1,
                'longitude': 1.1
            })
        self.hass.block_till_done()
        state = self.hass.states.get('proximity.home')
        assert state.state == '0'
        assert ((state.attributes.get('nearest') == 'test1, test2') or
                (state.attributes.get('nearest') == 'test2, test1'))
        assert state.attributes.get('dir_of_travel') == 'arrived'

    def test_device_tracker_test1_away(self):
        """Test for tracker state away."""
        config = {
            'proximity': {
                'home': {
                    'ignored_zones': [
                        'work'
                    ],
                    'devices': [
                        'device_tracker.test1',
                    ],
                    'tolerance': '1'
                }
            }
        }

        assert setup_component(self.hass, DOMAIN, config)

        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 20.1,
                'longitude': 10.1
            })

        self.hass.block_till_done()
        state = self.hass.states.get('proximity.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'unknown'

    def test_device_tracker_test1_awayfurther(self):
        """Test for tracker state away further."""
        config = {
            'proximity': {
                'home': {
                    'ignored_zones': [
                        'work'
                    ],
                    'devices': [
                        'device_tracker.test1',
                    ],
                    'tolerance': '1'
                }
            }
        }

        assert setup_component(self.hass, DOMAIN, config)

        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 20.1,
                'longitude': 10.1
            })
        self.hass.block_till_done()
        state = self.hass.states.get('proximity.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'unknown'

        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 40.1,
                'longitude': 20.1
            })
        self.hass.block_till_done()
        state = self.hass.states.get('proximity.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'towards'

    def test_device_tracker_test1_awaycloser(self):
        """Test for tracker state away closer."""
        config = {
            'proximity': {
                'home': {
                    'ignored_zones': [
                        'work'
                    ],
                    'devices': [
                        'device_tracker.test1',
                    ],
                    'tolerance': '1'
                }
            }
        }

        assert setup_component(self.hass, DOMAIN, config)

        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 40.1,
                'longitude': 20.1
            })
        self.hass.block_till_done()
        state = self.hass.states.get('proximity.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'unknown'

        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 20.1,
                'longitude': 10.1
            })
        self.hass.block_till_done()
        state = self.hass.states.get('proximity.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'away_from'

    def test_all_device_trackers_in_ignored_zone(self):
        """Test for tracker in ignored zone."""
        config = {
            'proximity': {
                'home': {
                    'ignored_zones': [
                        'work'
                    ],
                    'devices': [
                        'device_tracker.test1',
                    ],
                    'tolerance': '1'
                }
            }
        }

        assert setup_component(self.hass, DOMAIN, config)

        self.hass.states.set(
            'device_tracker.test1', 'work',
            {
                'friendly_name': 'test1'
            })
        self.hass.block_till_done()
        state = self.hass.states.get('proximity.home')
        assert state.state == 'not set'
        assert state.attributes.get('nearest') == 'not set'
        assert state.attributes.get('dir_of_travel') == 'not set'

    def test_device_tracker_test1_no_coordinates(self):
        """Test for tracker with no coordinates."""
        config = {
            'proximity': {
                'home': {
                    'ignored_zones': [
                        'work'
                    ],
                    'devices': [
                        'device_tracker.test1',
                    ],
                    'tolerance': '1'
                }
            }
        }

        assert setup_component(self.hass, DOMAIN, config)

        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1'
            })
        self.hass.block_till_done()
        state = self.hass.states.get('proximity.home')
        assert state.attributes.get('nearest') == 'not set'
        assert state.attributes.get('dir_of_travel') == 'not set'

    def test_device_tracker_test1_awayfurther_than_test2_first_test1(self):
        """Test for tracker ordering."""
        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1'
            })
        self.hass.block_till_done()
        self.hass.states.set(
            'device_tracker.test2', 'not_home',
            {
                'friendly_name': 'test2'
            })
        self.hass.block_till_done()

        assert proximity.setup(self.hass, {
            'proximity': {
                'home': {
                    'ignored_zones': [
                        'work'
                    ],
                    'devices': [
                        'device_tracker.test1',
                        'device_tracker.test2'
                    ],
                    'tolerance': '1',
                    'zone': 'home'
                }
            }
        })

        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 20.1,
                'longitude': 10.1
            })
        self.hass.block_till_done()
        state = self.hass.states.get('proximity.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'unknown'

        self.hass.states.set(
            'device_tracker.test2', 'not_home',
            {
                'friendly_name': 'test2',
                'latitude': 40.1,
                'longitude': 20.1
            })
        self.hass.block_till_done()
        state = self.hass.states.get('proximity.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'unknown'

    def test_device_tracker_test1_awayfurther_than_test2_first_test2(self):
        """Test for tracker ordering."""
        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1'
            })
        self.hass.block_till_done()
        self.hass.states.set(
            'device_tracker.test2', 'not_home',
            {
                'friendly_name': 'test2'
            })
        self.hass.block_till_done()
        assert proximity.setup(self.hass, {
            'proximity': {
                'home': {
                    'ignored_zones': [
                        'work'
                    ],
                    'devices': [
                        'device_tracker.test1',
                        'device_tracker.test2'
                    ],
                    'zone': 'home'

                }
            }
        })

        self.hass.states.set(
            'device_tracker.test2', 'not_home',
            {
                'friendly_name': 'test2',
                'latitude': 40.1,
                'longitude': 20.1
            })
        self.hass.block_till_done()
        state = self.hass.states.get('proximity.home')
        assert state.attributes.get('nearest') == 'test2'
        assert state.attributes.get('dir_of_travel') == 'unknown'

        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 20.1,
                'longitude': 10.1
            })
        self.hass.block_till_done()
        state = self.hass.states.get('proximity.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'unknown'

    def test_device_tracker_test1_awayfurther_test2_in_ignored_zone(self):
        """Test for tracker states."""
        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1'
            })
        self.hass.block_till_done()
        self.hass.states.set(
            'device_tracker.test2', 'work',
            {
                'friendly_name': 'test2'
            })
        self.hass.block_till_done()
        assert proximity.setup(self.hass, {
            'proximity': {
                'home': {
                    'ignored_zones': [
                        'work'
                    ],
                    'devices': [
                        'device_tracker.test1',
                        'device_tracker.test2'
                    ],
                    'zone': 'home'
                }
            }
        })

        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 20.1,
                'longitude': 10.1
            })
        self.hass.block_till_done()
        state = self.hass.states.get('proximity.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'unknown'

    def test_device_tracker_test1_awayfurther_test2_first(self):
        """Test for tracker state."""
        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1'
            })
        self.hass.block_till_done()
        self.hass.states.set(
            'device_tracker.test2', 'not_home',
            {
                'friendly_name': 'test2'
            })
        self.hass.block_till_done()

        assert proximity.setup(self.hass, {
            'proximity': {
                'home': {
                    'ignored_zones': [
                        'work'
                    ],
                    'devices': [
                        'device_tracker.test1',
                        'device_tracker.test2'
                    ],
                    'zone': 'home'
                }
            }
        })

        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 10.1,
                'longitude': 5.1
            })
        self.hass.block_till_done()

        self.hass.states.set(
            'device_tracker.test2', 'not_home',
            {
                'friendly_name': 'test2',
                'latitude': 20.1,
                'longitude': 10.1
            })
        self.hass.block_till_done()

        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 40.1,
                'longitude': 20.1
            })
        self.hass.block_till_done()

        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 35.1,
                'longitude': 15.1
            })
        self.hass.block_till_done()

        self.hass.states.set(
            'device_tracker.test1', 'work',
            {
                'friendly_name': 'test1'
            })
        self.hass.block_till_done()

        state = self.hass.states.get('proximity.home')
        assert state.attributes.get('nearest') == 'test2'
        assert state.attributes.get('dir_of_travel') == 'unknown'

    def test_device_tracker_test1_awayfurther_a_bit(self):
        """Test for tracker states."""
        assert proximity.setup(self.hass, {
            'proximity': {
                'home': {
                    'ignored_zones': [
                        'work'
                    ],
                    'devices': [
                        'device_tracker.test1'
                    ],
                    'tolerance': 1000,
                    'zone': 'home'
                }
            }
        })

        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 20.1000001,
                'longitude': 10.1000001
            })
        self.hass.block_till_done()
        state = self.hass.states.get('proximity.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'unknown'

        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 20.1000002,
                'longitude': 10.1000002
            })
        self.hass.block_till_done()
        state = self.hass.states.get('proximity.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'stationary'

    def test_device_tracker_test1_nearest_after_test2_in_ignored_zone(self):
        """Test for tracker states."""
        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1'
            })
        self.hass.block_till_done()
        self.hass.states.set(
            'device_tracker.test2', 'not_home',
            {
                'friendly_name': 'test2'
            })
        self.hass.block_till_done()

        assert proximity.setup(self.hass, {
            'proximity': {
                'home': {
                    'ignored_zones': [
                        'work'
                    ],
                    'devices': [
                        'device_tracker.test1',
                        'device_tracker.test2'
                    ],
                    'zone': 'home'
                }
            }
        })

        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 20.1,
                'longitude': 10.1
            })
        self.hass.block_till_done()
        state = self.hass.states.get('proximity.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'unknown'

        self.hass.states.set(
            'device_tracker.test2', 'not_home',
            {
                'friendly_name': 'test2',
                'latitude': 10.1,
                'longitude': 5.1
            })
        self.hass.block_till_done()
        state = self.hass.states.get('proximity.home')
        assert state.attributes.get('nearest') == 'test2'
        assert state.attributes.get('dir_of_travel') == 'unknown'

        self.hass.states.set(
            'device_tracker.test2', 'work',
            {
                'friendly_name': 'test2',
                'latitude': 12.6,
                'longitude': 7.6
            })
        self.hass.block_till_done()
        state = self.hass.states.get('proximity.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'unknown'
