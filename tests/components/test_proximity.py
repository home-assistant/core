# pylint: disable=too-many-lines
"""
tests.components.proximity
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests proximity component.
"""

import os
from datetime import timedelta
from homeassistant.components import proximity
from homeassistant.components import zone
import homeassistant.components.device_tracker as device_tracker
from tests.common import get_test_home_assistant


class TestProximity:
    # pylint: disable=too-many-public-methods
    """ Test the Proximity component. """

    def setup_method(self, method):
        """ setup tests """
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
        """ Test the Proximity component setup """
        assert proximity.setup(self.hass, {
            'proximity': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'test1',
                        'test2'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'test1',
                        'test2'
                    },
                    'tolerance': 1
                }
            }
        })

        state = self.hass.states.get('proximity.home')
        assert state.state != 'not set'
        assert state.attributes.get('nearest') != 'not set'
        assert state.attributes.get('dir_of_travel') != 'not set'

    def test_proximity_device(self):
        """ Test the Proximity component setup for devices """
        assert proximity.setup(self.hass, {
            'proximity': {
                'test1': {
                    'zones': {
                        'home',
                        'work'
                    },
                    'type': 'device',
                    'device': 'test1',
                    'tolerance': 1
                },
                'test2': {
                    'zones': {
                        'home',
                        'work'
                    },
                    'type': 'device',
                    'device': 'test2',
                    'tolerance': 1
                }
            }
        })

        state = self.hass.states.get('proximity.test1')
        assert state.state != 'not set'
        assert state.attributes.get('dist_to_zone') != 'not set'
        assert state.attributes.get('dir_of_travel') != 'not set'

    def test_device_1(self):
        """ Test no device for device tracker """
        assert not proximity.setup(self.hass, {
            'proximity': {
                'test1': {
                    'zones': {
                        'home',
                        'work'
                    },
                    'type': 'device',
                    'tolerance': 1
                },
                'test2': {
                    'zones': {
                        'home',
                        'work'
                    },
                    'type': 'device',
                    'tolerance': 1
                }
            }
        })

    def test_device_2(self):
        """ Test no zones for device tracker """
        assert not proximity.setup(self.hass, {
            'proximity': {
                'test1': {
                    'type': 'device',
                    'device': 'test1',
                    'tolerance': 1
                },
                'test2': {
                    'type': 'device',
                    'device': 'test2',
                    'tolerance': 1
                }
            }
        })

    def test_device_3(self):
        """ Test no initial state for device tracker """
        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1'
            })
        self.hass.pool.block_till_done()

        assert proximity.setup(self.hass, {
            'proximity': {
                'test1': {
                    'zones': {
                        'home',
                        'work'
                    },
                    'type': 'device',
                    'device': 'test1',
                    'tolerance': 1
                },
                'test2': {
                    'zones': {
                        'home',
                        'work'
                    },
                    'type': 'device',
                    'device': 'test2',
                    'tolerance': 1
                }
            }
        })

        state = self.hass.states.get('proximity.test1')
        assert state.state == 'not set'
        assert state.attributes.get('dist_to_zone') == 'not set'
        assert state.attributes.get('dir_of_travel') == 'not set'

    def test_device_4(self):
        """ Test no coordinates in new state for device tracker """
        assert proximity.setup(self.hass, {
            'proximity': {
                'test1': {
                    'zones': {
                        'home',
                        'work'
                    },
                    'type': 'device',
                    'device': 'test1',
                    'tolerance': 1
                },
                'test2': {
                    'zones': {
                        'home',
                        'work'
                    },
                    'type': 'device',
                    'device': 'test2',
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

        state = self.hass.states.get('proximity.test1')
        assert state.state != 'not set'
        assert state.attributes.get('dist_to_zone') != 'not set'
        assert state.attributes.get('dir_of_travel') != 'not set'

    def test_device_5(self):
        """ Test device in a zone for device tracker """
        assert proximity.setup(self.hass, {
            'proximity': {
                'test1': {
                    'zones': {
                        'home',
                        'work'
                    },
                    'type': 'device',
                    'device': 'test1',
                    'tolerance': 1
                },
                'test2': {
                    'zones': {
                        'home',
                        'work'
                    },
                    'type': 'device',
                    'device': 'test2',
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

        state = self.hass.states.get('proximity.test1')
        assert state.state == 'home'
        assert state.attributes.get('dist_to_zone') == 0
        assert state.attributes.get('dir_of_travel') == 'arrived'

    def test_device_6(self):
        """ Test device moving for device tracker """
        assert proximity.setup(self.hass, {
            'proximity': {
                'test1': {
                    'zones': {
                        'home',
                        'work'
                    },
                    'type': 'device',
                    'device': 'test1',
                    'tolerance': 1
                },
                'test2': {
                    'zones': {
                        'home',
                        'work'
                    },
                    'type': 'device',
                    'device': 'test2',
                    'tolerance': 1
                }
            }
        })

        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 70,
                'longitude': 70
            })
        self.hass.pool.block_till_done()

        state = self.hass.states.get('proximity.test1')
        assert state.state == 'home'
        assert state.attributes.get('dist_to_zone') != 0
        assert state.attributes.get('dir_of_travel') == 'away_from'

    def test_device_7(self):
        """ Test device moving further for device tracker """
        assert proximity.setup(self.hass, {
            'proximity': {
                'test1': {
                    'zones': {
                        'home',
                        'work'
                    },
                    'type': 'device',
                    'device': 'test1',
                    'tolerance': 1
                },
                'test2': {
                    'zones': {
                        'home',
                        'work'
                    },
                    'type': 'device',
                    'device': 'test2',
                    'tolerance': 1
                }
            }
        })

        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 70,
                'longitude': 70
            })
        self.hass.pool.block_till_done()

        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 80,
                'longitude': 80
            })
        self.hass.pool.block_till_done()

        state = self.hass.states.get('proximity.test1')
        assert state.state == 'home'
        assert state.attributes.get('dist_to_zone') != 0
        assert state.attributes.get('dir_of_travel') == 'away_from'

    def test_device_8(self):
        """ Test device moving closer for device tracker """
        assert proximity.setup(self.hass, {
            'proximity': {
                'test1': {
                    'zones': {
                        'home',
                        'work'
                    },
                    'type': 'device',
                    'device': 'test1',
                    'tolerance': 1
                },
                'test2': {
                    'zones': {
                        'home',
                        'work'
                    },
                    'type': 'device',
                    'device': 'test2',
                    'tolerance': 1
                }
            }
        })

        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 80,
                'longitude': 80
            })
        self.hass.pool.block_till_done()

        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 70,
                'longitude': 70
            })
        self.hass.pool.block_till_done()

        state = self.hass.states.get('proximity.test1')
        assert state.state == 'home'
        assert state.attributes.get('dist_to_zone') != 0
        assert state.attributes.get('dir_of_travel') == 'towards'

    def test_device_9(self):
        """ Test device moving a bit for device tracker """
        assert proximity.setup(self.hass, {
            'proximity': {
                'test1': {
                    'zones': {
                        'home',
                        'work'
                    },
                    'type': 'device',
                    'device': 'test1',
                    'tolerance': 100
                },
                'test2': {
                    'zones': {
                        'home',
                        'work'
                    },
                    'type': 'device',
                    'device': 'test2',
                    'tolerance': 1
                }
            }
        })

        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 70,
                'longitude': 70
            })
        self.hass.pool.block_till_done()

        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 70.0001,
                'longitude': 70
            })
        self.hass.pool.block_till_done()

        state = self.hass.states.get('proximity.test1')
        assert state.state == 'home'
        assert state.attributes.get('dist_to_zone') != 0
        assert state.attributes.get('dir_of_travel') == 'stationary'

    def test_no_config(self):
        """ Test no config given """
        assert not proximity.setup(self.hass, {
        })

    def test_no_proximity_config(self):
        """ Test no proximity config given """
        assert not proximity.setup(self.hass, {
            'proximity': {
                'home': 'test'
            }
        })

    def test_zone_1(self):
        """ Test no devices for zone tracker """
        assert not proximity.setup(self.hass, {
            'proximity': {
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

    def test_zone_2(self):
        """ Test no tolerance for zone tracker """
        assert proximity.setup(self.hass, {
            'proximity': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'test1',
                        'test2'
                    }
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'test1',
                        'test2'
                    }
                }
            }
        })

    def test_zone_3(self):
        """ Test no ignored zones for zone tracker """
        assert proximity.setup(self.hass, {
            'proximity': {
                'home': {
                    'zone': 'home',
                    'devices': {
                        'test1',
                        'test2'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'devices': {
                        'test1',
                        'test2'
                    },
                    'tolerance': 1
                }
            }
        })

    def test_zone_4(self):
        """ Test no zone for zone tracker """
        assert proximity.setup(self.hass, {
            'proximity': {
                'home': {
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'test1',
                        'test2'
                    },
                    'tolerance': 1
                },
                'work': {
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'test1',
                        'test2'
                    },
                    'tolerance': 1
                }
            }
        })

    def test_zone_5(self):
        """ Test device in monitored zone for zone tracker """
        assert proximity.setup(self.hass, {
            'proximity': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'test1'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'test1',
                        'test2'
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

        state = self.hass.states.get('proximity.home')
        assert state.state == '0'
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'arrived'

    def test_zone_6(self):
        """ Test device in monitored zone initial for zone tracker """
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
        assert proximity.setup(self.hass, {
            'proximity': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'test1',
                        'test2'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'test1',
                        'test2'
                    },
                    'tolerance': 1
                }
            }
        })

        state = self.hass.states.get('proximity.home')
        assert state.state == '0'
        assert ((state.attributes.get('nearest') == 'test1, test2') or
                (state.attributes.get('nearest') == 'test2, test1'))
        assert state.attributes.get('dir_of_travel') == 'arrived'

    def test_zone_7(self):
        """ Test devices in zone for zone tracker """
        assert proximity.setup(self.hass, {
            'proximity': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'test1',
                        'test2'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'test1',
                        'test2'
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
        state = self.hass.states.get('proximity.home')
        assert state.state == '0'
        assert ((state.attributes.get('nearest') == 'test1, test2') or
                (state.attributes.get('nearest') == 'test2, test1'))
        assert state.attributes.get('dir_of_travel') == 'arrived'

    def test_zone_8(self):
        """ Test device away for zone tracker """
        assert proximity.setup(self.hass, {
            'proximity': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'test1'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'test1',
                        'test2'
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
        state = self.hass.states.get('proximity.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'towards'

    def test_zone_9(self):
        """ Test device moving away for zone tracker """
        assert proximity.setup(self.hass, {
            'proximity': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'test1'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'test1',
                        'test2'
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
        state = self.hass.states.get('proximity.home')
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
        state = self.hass.states.get('proximity.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'away_from'

    def test_zone_10(self):
        """ Test device moving closer for zone tracker """
        assert proximity.setup(self.hass, {
            'proximity': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'test1'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'test1',
                        'test2'
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
        state = self.hass.states.get('proximity.home')
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
        state = self.hass.states.get('proximity.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'towards'

    def test_zone_11(self):
        """ Test all devices in ignored zone for zone tracker """
        assert proximity.setup(self.hass, {
            'proximity': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'test1'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'test1',
                        'test2'
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
        state = self.hass.states.get('proximity.home')
        assert state.state == 'not set'
        assert state.attributes.get('nearest') == 'not set'
        assert state.attributes.get('dir_of_travel') == 'not set'

    def test_zone_12(self):
        """ Test all devices in ignored zone initial for zone tracker """
        self.hass.states.set(
            'device_tracker.test1', 'work',
            {
                'friendly_name': 'test1',
                'latitude': 100,
                'longitude': 100
            })
        self.hass.pool.block_till_done()

        assert proximity.setup(self.hass, {
            'proximity': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'test1',
                        'test2'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'test1',
                        'test2'
                    },
                    'tolerance': 1
                }
            }
        })

        state = self.hass.states.get('proximity.home')
        assert state.attributes.get('nearest') == 'test2'
        assert state.attributes.get('dir_of_travel') == 'unknown'

    def test_zone_13(self):
        """ Test new state no coordinates for zone tracker """
        assert proximity.setup(self.hass, {
            'proximity': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'test1'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'test1',
                        'test2'
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
        state = self.hass.states.get('proximity.home')
        assert state.attributes.get('nearest') == 'not set'
        assert state.attributes.get('dir_of_travel') == 'not set'

    def test_zone_14(self):
        """ Test initial no coordinates for zone tracker """
        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1'
            })
        self.hass.pool.block_till_done()

        assert proximity.setup(self.hass, {
            'proximity': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'test1'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'test1',
                        'test2'
                    },
                    'tolerance': 1
                }
            }
        })

        state = self.hass.states.get('proximity.home')
        assert state.attributes.get('nearest') == 'not set'
        assert state.attributes.get('dir_of_travel') == 'not set'

    def test_zone_15(self):
        """ Test two devices moving, closest changes for zone tracker """
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
        assert proximity.setup(self.hass, {
            'proximity': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'test1',
                        'test2'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'test1',
                        'test2'
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
        self.hass.pool.block_till_done()
        state = self.hass.states.get('proximity.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'unknown'

    def test_zone_16(self):
        """ Test two devices moving, last remains closest for zone tracker """
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
        assert proximity.setup(self.hass, {
            'proximity': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'test1',
                        'test2'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'test1',
                        'test2'
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
        self.hass.pool.block_till_done()
        state = self.hass.states.get('proximity.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'unknown'

    def test_zone_17(self):
        """ Test devices goes in ignored zone for zone tracker """
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
        assert proximity.setup(self.hass, {
            'proximity': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'test1',
                        'test2'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'test1',
                        'test2'
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
        state = self.hass.states.get('proximity.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'unknown'

    def test_zone_18(self):
        """ Test devices moving around for zone tracker """
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
        assert proximity.setup(self.hass, {
            'proximity': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'test1',
                        'test2'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'test1',
                        'test2'
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
        state = self.hass.states.get('proximity.home')
        assert state.attributes.get('nearest') == 'test2'
        assert state.attributes.get('dir_of_travel') == 'unknown'

    def test_zone_19(self):
        """ Test device moves a bit for zone tracker """
        assert proximity.setup(self.hass, {
            'proximity': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'test1'
                    },
                    'tolerance': 1000
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'test1',
                        'test2'
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
        state = self.hass.states.get('proximity.home')
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
        state = self.hass.states.get('proximity.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'stationary'

    def test_zone_20(self):
        """ Test closest device goes in ignored zone for zone tracker """
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
        assert proximity.setup(self.hass, {
            'proximity': {
                'home': {
                    'zone': 'home',
                    'ignored_zones': {
                        'work'
                    },
                    'devices': {
                        'test1',
                        'test2'
                    },
                    'tolerance': 1
                },
                'work': {
                    'zone': 'work',
                    'ignored_zones': {
                        'home'
                    },
                    'devices': {
                        'test1',
                        'test2'
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
        self.hass.pool.block_till_done()
        state = self.hass.states.get('proximity.home')
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
        state = self.hass.states.get('proximity.home')
        assert state.attributes.get('nearest') == 'test1'
        assert state.attributes.get('dir_of_travel') == 'unknown'
