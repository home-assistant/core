"""
tests.components.proximity_zones
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests proximity_zones component.
"""

import os
from homeassistant.components import proximity_zones
from homeassistant.components import zone
import homeassistant.components.device_tracker as device_tracker
from datetime import timedelta
from tests.common import get_test_home_assistant

class TestProximityZones:
    """ Test the Proximity_zones component. """


    def setup_method(self, method):
        self.hass = get_test_home_assistant()

        self.yaml_devices = self.hass.config.path(device_tracker.YAML_DEVICES)

        zone.setup(self.hass, {
            'zone': [
                {
                    'name': 'home',
                    'latitude': 2.1,
                    'longitude': 1.1,
                    'radius': 10,
                },
                {
                    'name': 'work',
                    'latitude': 100,
                    'longitude': 100,
                    'radius': 10,
                },
            ]
        })

        dev_id = 'test1'
        friendly_name = 'test1'
        picture = 'http://placehold.it/200x200'

        device = device_tracker.Device(
            self.hass,
            timedelta(seconds=180),
            0,
            True,
            dev_id,
            None,
            friendly_name,
            picture,
            away_hide=True)
        device_tracker.update_config(self.yaml_devices, dev_id, device)

        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 50,
                'longitude': 50
            })

        dev_id = 'test2'
        friendly_name = 'test2'
        picture = 'http://placehold.it/200x200'

        device = device_tracker.Device(
            self.hass, timedelta(seconds=180), 0, True, dev_id, None,
            friendly_name, picture, away_hide=True)
        device_tracker.update_config(self.yaml_devices, dev_id, device)

        self.hass.states.set(
            'device_tracker.test2', 'not_home',
            {
                'friendly_name': 'test2',
                'latitude': 50,
                'longitude': 50
            })

    def teardown_method(self, method):
        """ Stop down stuff we started. """
        self.hass.stop()

        try:
            os.remove(self.hass.config.path(device_tracker.YAML_DEVICES))
        except FileNotFoundError:
            pass

    def test_proximity(self):
        assert proximity_zones.setup(self.hass, {
            'proximity_zones': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    },
                    'tolerance': 1
                }
            }
        })

        state = self.hass.states.get('proximity_zones.home')
        assert state.state != 'not set'
        assert state.attributes.get('nearest') != 'not set'
        assert state.attributes.get('dir_of_travel') != 'not set'

    def test_no_config(self):
        assert not proximity_zones.setup(self.hass, {
        })

    def test_no_proximity_config(self):
        assert not proximity_zones.setup(self.hass, {
            'proximity_zones': {
                'home': 'test'
            }
        })

    def test_no_devices_in_config(self):
        assert not proximity_zones.setup(self.hass, {
            'proximity_zones': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'tolerance': 1
                }
            }
        })

    def test_no_tolerance_in_config(self):
        assert proximity_zones.setup(self.hass, {
            'proximity_zones': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    }
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    }
                }
            }
        })

    def test_no_ignored_zones_in_config(self):
        assert proximity_zones.setup(self.hass, {
            'proximity_zones': {
                'home': {
                    'zone': 'home',
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    },
                    'tolerance': 1
                }
            }
        })

    def test_no_zone_in_config(self):
        assert proximity_zones.setup(self.hass, {
            'proximity_zones': {
                'home': {
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    },
                    'tolerance': 1
                },
                'work': {
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    },
                    'tolerance': 1
                }
            }
        })

    def test_device_tracker_test1_in_zone(self):
        assert proximity_zones.setup(self.hass, {
            'proximity_zones': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'device_tracker.test1'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    },
                    'tolerance': 1
                }
            }
        })

        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 50,
                'longitude': 50
            })
        self.hass.pool.block_till_done()

        state = self.hass.states.get('device_tracker.test1')
        assert state.state == 'not_home'

        self.hass.states.set(
            'device_tracker.test1', 'home',
            {
                'friendly_name': 'test1',
                'latitude': 2.1,
                'longitude': 1.1
            })
        self.hass.pool.block_till_done()

        device_state = self.hass.states.get('device_tracker.test1')
        assert device_state.state == 'home'
        device_state_lat = device_state.attributes['latitude']
        assert device_state_lat == 2.1
        device_state_lon = device_state.attributes['longitude']
        assert device_state_lon == 1.1

        zone_state = self.hass.states.get('zone.home')
        assert zone_state.state == 'zoning'
        proximity_latitude = zone_state.attributes.get('latitude')
        assert proximity_latitude == 2.1
        proximity_longitude = zone_state.attributes.get('longitude')
        assert proximity_longitude == 1.1

        assert zone.in_zone(zone_state, device_state_lat, device_state_lon)

        state = self.hass.states.get('proximity_zones.home')
        assert state.state == '0'
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'arrived'

    def test_device_trackers_in_zone_at_start(self):
        self.hass.states.set(
            'device_tracker.test1', 'home',
            {
                'friendly_name': 'test1',
                'latitude': 2.1,
                'longitude': 1.1
            })
        self.hass.pool.block_till_done()
        self.hass.states.set(
            'device_tracker.test2', 'home',
            {
                'friendly_name': 'test2',
                'latitude': 2.1,
                'longitude': 1.1
            })
        self.hass.pool.block_till_done()
        assert proximity_zones.setup(self.hass, {
            'proximity_zones': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    },
                    'tolerance': 1
                }
            }
        })

        state = self.hass.states.get('proximity_zones.home')
        assert state.state == '0'
        assert ((state.attributes.get('nearest') == 'test1, test2') or
                (state.attributes.get('nearest') == 'test2, test1'))
        assert state.attributes.get('dir_of_travel') == 'arrived'

    def test_device_trackers_in_zone(self):
        assert proximity_zones.setup(self.hass, {
            'proximity_zones': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    },
                    'tolerance': 1
                }
            }
        })
        self.hass.states.set(
            'device_tracker.test1', 'home',
            {
                'friendly_name': 'test1',
                'latitude': 2.1,
                'longitude': 1.1
            })
        self.hass.pool.block_till_done()
        self.hass.states.set(
            'device_tracker.test2', 'home',
            {
                'friendly_name': 'test2',
                'latitude': 2.1,
                'longitude': 1.1
            })
        self.hass.pool.block_till_done()
        state = self.hass.states.get('proximity_zones.home')
        assert state.state == '0'
        assert ((state.attributes.get('nearest') == 'test1, test2') or
                (state.attributes.get('nearest') == 'test2, test1'))
        assert state.attributes.get('dir_of_travel') == 'arrived'

    def test_device_tracker_test1_away(self):
        assert proximity_zones.setup(self.hass, {
            'proximity_zones': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'device_tracker.test1'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    },
                    'tolerance': 1
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
        self.hass.pool.block_till_done()
        state = self.hass.states.get('proximity_zones.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'towards'

    def test_device_tracker_test1_awayfurther(self):
        assert proximity_zones.setup(self.hass, {
            'proximity_zones': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'device_tracker.test1'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    },
                    'tolerance': 1
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
        self.hass.pool.block_till_done()
        state = self.hass.states.get('proximity_zones.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'towards'
        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 40.1,
                'longitude': 20.1
            })
        self.hass.pool.block_till_done()
        state = self.hass.states.get('proximity_zones.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'away_from'

    def test_device_tracker_test1_awaycloser(self):
        assert proximity_zones.setup(self.hass, {
            'proximity_zones': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'device_tracker.test1'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    },
                    'tolerance': 1
                }
            }
        })

        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 40.1,
                'longitude': 20.1
            })
        self.hass.pool.block_till_done()
        state = self.hass.states.get('proximity_zones.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'towards'
        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 20.1,
                'longitude': 10.1
            })
        self.hass.pool.block_till_done()
        state = self.hass.states.get('proximity_zones.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'towards'

    def test_all_device_trackers_in_ignored_zone(self):
        assert proximity_zones.setup(self.hass, {
            'proximity_zones': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'device_tracker.test1'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    },
                    'tolerance': 1
                }
            }
        })

        self.hass.states.set(
            'device_tracker.test1', 'work',
            {
                'friendly_name': 'test1',
                'latitude': 100,
                'longitude': 100
            })
        self.hass.pool.block_till_done()
        state = self.hass.states.get('proximity_zones.home')
        assert state.state == 'not set'
        assert state.attributes.get('nearest') == 'not set'
        assert state.attributes.get('dir_of_travel') == 'not set'

    def test_all_device_trackers_in_ignored_zone_at_start(self):
        self.hass.states.set(
            'device_tracker.test1', 'work',
            {
                'friendly_name': 'test1',
                'latitude': 100,
                'longitude': 100
            })
        self.hass.pool.block_till_done()

        assert proximity_zones.setup(self.hass, {
            'proximity_zones': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    },
                    'tolerance': 1
                }
            }
        })

        state = self.hass.states.get('proximity_zones.home')
        assert state.attributes.get('nearest') == 'test2'
        assert state.attributes.get('dir_of_travel') == 'unknown'

    def test_device_tracker_test1_no_coordinates(self):
        assert proximity_zones.setup(self.hass, {
            'proximity_zones': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'device_tracker.test1'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    },
                    'tolerance': 1
                }
            }
        })

        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1'
            })
        self.hass.pool.block_till_done()
        state = self.hass.states.get('proximity_zones.home')
        assert state.attributes.get('nearest') == 'not set'
        assert state.attributes.get('dir_of_travel') == 'not set'

    def test_device_tracker_test1_no_coordinates_at_start(self):
        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1'
            })
        self.hass.pool.block_till_done()

        assert proximity_zones.setup(self.hass, {
            'proximity_zones': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'device_tracker.test1'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    },
                    'tolerance': 1
                }
            }
        })

        state = self.hass.states.get('proximity_zones.home')
        assert state.attributes.get('nearest') == 'not set'
        assert state.attributes.get('dir_of_travel') == 'not set'

    def test_device_tracker_test1_awayfurther_than_test2_first_test1(self):
        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1'
            })
        self.hass.pool.block_till_done()
        self.hass.states.set(
            'device_tracker.test2', 'not_home',
            {
                'friendly_name': 'test2'
            })
        self.hass.pool.block_till_done()
        assert proximity_zones.setup(self.hass, {
            'proximity_zones': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    },
                    'tolerance': 1
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
        self.hass.pool.block_till_done()
        state = self.hass.states.get('proximity_zones.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'unknown'
        self.hass.states.set(
            'device_tracker.test2', 'not_home',
            {
                'friendly_name': 'test2',
                'latitude': 40.1,
                'longitude': 20.1
            })
        self.hass.pool.block_till_done()
        state = self.hass.states.get('proximity_zones.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'unknown'

    def test_device_tracker_test1_awayfurther_than_test2_first_test2(self):
        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1'
            })
        self.hass.pool.block_till_done()
        self.hass.states.set(
            'device_tracker.test2', 'not_home',
            {
                'friendly_name': 'test2'
            })
        self.hass.pool.block_till_done()
        assert proximity_zones.setup(self.hass, {
            'proximity_zones': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    },
                    'tolerance': 1
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
        self.hass.pool.block_till_done()
        state = self.hass.states.get('proximity_zones.home')
        assert state.attributes.get('nearest') == 'test2'
        assert state.attributes.get('dir_of_travel') == 'unknown'
        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 20.1,
                'longitude': 10.1
            })
        self.hass.pool.block_till_done()
        state = self.hass.states.get('proximity_zones.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'unknown'

    def test_device_tracker_test1_awayfurther_test2_in_ignored_zone(self):
        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1'
            })
        self.hass.pool.block_till_done()
        self.hass.states.set(
            'device_tracker.test2', 'work',
            {
                'friendly_name': 'test2',
                'latitude': 100,
                'longitude': 100
            })
        self.hass.pool.block_till_done()
        assert proximity_zones.setup(self.hass, {
            'proximity_zones': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    },
                    'tolerance': 1
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
        self.hass.pool.block_till_done()
        state = self.hass.states.get('proximity_zones.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'unknown'

    def test_device_tracker_test1_awayfurther_test2_first(self):
        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1'
            })
        self.hass.pool.block_till_done()
        self.hass.states.set(
            'device_tracker.test2', 'not_home',
            {
                'friendly_name': 'test2'
            })
        self.hass.pool.block_till_done()
        assert proximity_zones.setup(self.hass, {
            'proximity_zones': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    },
                    'tolerance': 1
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
        self.hass.pool.block_till_done()

        self.hass.states.set(
            'device_tracker.test2', 'not_home',
            {
                'friendly_name': 'test2',
                'latitude': 20.1,
                'longitude': 10.1
            })
        self.hass.pool.block_till_done()
        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 40.1,
                'longitude': 20.1
            })
        self.hass.pool.block_till_done()
        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 35.1,
                'longitude': 15.1
            })
        self.hass.pool.block_till_done()
        self.hass.states.set(
            'device_tracker.test1', 'work',
            {
                'friendly_name': 'test1',
                'latitude': 100,
                'longitude': 100
            })
        self.hass.pool.block_till_done()
        state = self.hass.states.get('proximity_zones.home')
        assert state.attributes.get('nearest') == 'test2'
        assert state.attributes.get('dir_of_travel') == 'unknown'

    def test_device_tracker_test1_awayfurther_a_bit(self):
        assert proximity_zones.setup(self.hass, {
            'proximity_zones': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'device_tracker.test1'
                    },
                    'tolerance': 1000
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    },
                    'tolerance': 1
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
        self.hass.pool.block_till_done()
        state = self.hass.states.get('proximity_zones.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'towards'
        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 20.1000002,
                'longitude': 10.1000002
            })
        self.hass.pool.block_till_done()
        state = self.hass.states.get('proximity_zones.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'stationary'

    def test_device_tracker_test1_nearest_after_test2_in_ignored_zone(self):
        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1'
            })
        self.hass.pool.block_till_done()
        self.hass.states.set(
            'device_tracker.test2', 'not_home',
            {
                'friendly_name': 'test2'
            })
        self.hass.pool.block_till_done()
        assert proximity_zones.setup(self.hass, {
            'proximity_zones': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'device_tracker.test1',
                        'device_tracker.test2'
                    },
                    'tolerance': 1
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
        self.hass.pool.block_till_done()
        state = self.hass.states.get('proximity_zones.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'unknown'

        self.hass.states.set(
            'device_tracker.test2', 'not_home',
            {
                'friendly_name': 'test2',
                'latitude': 10.1,
                'longitude': 5.1
            })
        self.hass.pool.block_till_done()
        state = self.hass.states.get('proximity_zones.home')
        assert state.attributes.get('nearest') == 'test2'
        assert state.attributes.get('dir_of_travel') == 'unknown'

        self.hass.states.set(
            'device_tracker.test2', 'work',
            {
                'friendly_name': 'test2',
                'latitude': 100,
                'longitude': 100
            })
        self.hass.pool.block_till_done()
        state = self.hass.states.get('proximity_zones.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'unknown'
