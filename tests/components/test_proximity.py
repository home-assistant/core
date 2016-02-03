"""
tests.components.proximity
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests proximity component.
"""

import homeassistant.core as ha
from homeassistant.components import proximity

class TestProximity:
    """ Test the Proximity component. """

    def setup_method(self, method):
        self.hass = ha.HomeAssistant()
        self.hass.states.set(
            'zone.home', 'zoning',
            {
                'name': 'home',
                'latitude': 2.1,
                'longitude': 1.1,
                'radius': 10
            })

    def teardown_method(self, method):
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_proximity(self):
        assert proximity.setup(self.hass, {
            'proximity': {
                'zone': 'home',
                'devices': {
                    '- device_tracker.test1',
                    '- device_tracker.test2'
                }
            }
        })

        state = self.hass.states.get('proximity.home')
        assert state.state == 'not set'

        self.hass.states.set('proximity.home', '0')
        self.hass.pool.block_till_done()
        state = self.hass.states.get('proximity.home')
        assert state.state == '0'
    
    def device_tracker_test1_in_zone(self):
        self.hass.states.set(
            'device_tracker.test1', 'home',
            {
                'friendly_name': 'test1',
                'latitude': 2.1,
                'longitude': 1.1
            })
        state = self.hass.states.get('proximity.home')
        assert state.state == '0'
        assert state.attributes.get('nearest') == 'test1'
        assert started.attributes.get('dir_of_travel') == 'arrived'
        
    def device_trackers_in_zone(self):
        self.hass.states.set(
            'device_tracker.test1', 'home',
            {
                'friendly_name': 'test1',
                'latitude': 2.1,
                'longitude': 1.1
            })
        self.hass.states.set(
            'device_tracker.test2', 'home',
            {
                'friendly_name': 'test2',
                'latitude': 2.1,
                'longitude': 1.1
            })
        state = self.hass.states.get('proximity.home')
        assert state.state == '0'
        assert state.attributes.get('nearest') == 'test1, test2'
        assert started.attributes.get('dir_of_travel') == 'arrived'
        
    def device_tracker_test1_away(self):
        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'latitude': 20.1,
                'longitude': 10.1
            })
        state = self.hass.states.get('proximity.home')
        assert state.attributes.get('nearest') == 'test1'
        assert started.attributes.get('dir_of_travel') == 'unknown'