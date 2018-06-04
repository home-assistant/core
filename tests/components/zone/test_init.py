"""Test zone component."""

import unittest
from unittest.mock import Mock

from homeassistant import setup
from homeassistant.components import zone

from tests.common import get_test_home_assistant
from tests.common import MockConfigEntry


async def test_setup_entry_successful(hass):
    """Test setup entry is successful."""
    entry = Mock()
    entry.data = {
        zone.CONF_NAME: 'Test Zone',
        zone.CONF_LATITUDE: 1.1,
        zone.CONF_LONGITUDE: -2.2,
        zone.CONF_RADIUS: 250,
        zone.CONF_RADIUS: True
    }
    hass.data[zone.DOMAIN] = {}
    assert await zone.async_setup_entry(hass, entry) is True
    assert 'test_zone' in hass.data[zone.DOMAIN]


async def test_unload_entry_successful(hass):
    """Test unload entry is successful."""
    entry = Mock()
    entry.data = {
        zone.CONF_NAME: 'Test Zone',
        zone.CONF_LATITUDE: 1.1,
        zone.CONF_LONGITUDE: -2.2
    }
    hass.data[zone.DOMAIN] = {}
    assert await zone.async_setup_entry(hass, entry) is True
    assert await zone.async_unload_entry(hass, entry) is True
    assert not hass.data[zone.DOMAIN]


class TestComponentZone(unittest.TestCase):
    """Test the zone component."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_setup_no_zones_still_adds_home_zone(self):
        """Test if no config is passed in we still get the home zone."""
        assert setup.setup_component(self.hass, zone.DOMAIN, {'zone': None})
        assert len(self.hass.states.entity_ids('zone')) == 1
        state = self.hass.states.get('zone.home')
        assert self.hass.config.location_name == state.name
        assert self.hass.config.latitude == state.attributes['latitude']
        assert self.hass.config.longitude == state.attributes['longitude']
        assert not state.attributes.get('passive', False)
        assert 'test_home' in self.hass.data[zone.DOMAIN]

    def test_setup(self):
        """Test a successful setup."""
        info = {
            'name': 'Test Zone',
            'latitude': 32.880837,
            'longitude': -117.237561,
            'radius': 250,
            'passive': True
        }
        assert setup.setup_component(self.hass, zone.DOMAIN, {'zone': info})

        assert len(self.hass.states.entity_ids('zone')) == 2
        state = self.hass.states.get('zone.test_zone')
        assert info['name'] == state.name
        assert info['latitude'] == state.attributes['latitude']
        assert info['longitude'] == state.attributes['longitude']
        assert info['radius'] == state.attributes['radius']
        assert info['passive'] == state.attributes['passive']
        assert 'test_zone' in self.hass.data[zone.DOMAIN]
        assert 'test_home' in self.hass.data[zone.DOMAIN]

    def test_setup_zone_skips_home_zone(self):
        """Test that zone named Home should override hass home zone."""
        info = {
            'name': 'Home',
            'latitude': 1.1,
            'longitude': -2.2,
        }
        assert setup.setup_component(self.hass, zone.DOMAIN, {'zone': info})

        assert len(self.hass.states.entity_ids('zone')) == 1
        state = self.hass.states.get('zone.home')
        assert info['name'] == state.name
        assert 'home' in self.hass.data[zone.DOMAIN]
        assert 'test_home' not in self.hass.data[zone.DOMAIN]

    def test_setup_registered_zone_skips_home_zone(self):
        """Test that config entry named home should override hass home zone."""
        entry = MockConfigEntry(domain=zone.DOMAIN, data={
            zone.CONF_NAME: 'home'
        })
        entry.add_to_hass(self.hass)
        assert setup.setup_component(self.hass, zone.DOMAIN, {'zone': None})
        assert len(self.hass.states.entity_ids('zone')) == 0
        assert not self.hass.data[zone.DOMAIN]

    def test_setup_registered_zone_skips_configured_zone(self):
        """Test if config entry will override configured zone."""
        entry = MockConfigEntry(domain=zone.DOMAIN, data={
            zone.CONF_NAME: 'Test Zone'
        })
        entry.add_to_hass(self.hass)
        info = {
            'name': 'Test Zone',
            'latitude': 1.1,
            'longitude': -2.2,
        }
        assert setup.setup_component(self.hass, zone.DOMAIN, {'zone': info})

        assert len(self.hass.states.entity_ids('zone')) == 1
        state = self.hass.states.get('zone.test_zone')
        assert not state
        assert 'test_zone' not in self.hass.data[zone.DOMAIN]
        assert 'test_home' in self.hass.data[zone.DOMAIN]

    def test_active_zone_skips_passive_zones(self):
        """Test active and passive zones."""
        assert setup.setup_component(self.hass, zone.DOMAIN, {
            'zone': [
                {
                    'name': 'Passive Zone',
                    'latitude': 32.880600,
                    'longitude': -117.237561,
                    'radius': 250,
                    'passive': True
                },
            ]
        })
        self.hass.block_till_done()
        active = zone.zone.active_zone(self.hass, 32.880600, -117.237561)
        assert active is None

    def test_active_zone_skips_passive_zones_2(self):
        """Test active and passive zones."""
        assert setup.setup_component(self.hass, zone.DOMAIN, {
            'zone': [
                {
                    'name': 'Active Zone',
                    'latitude': 32.880800,
                    'longitude': -117.237561,
                    'radius': 500,
                },
            ]
        })
        self.hass.block_till_done()
        active = zone.zone.active_zone(self.hass, 32.880700, -117.237561)
        assert 'zone.active_zone' == active.entity_id

    def test_active_zone_prefers_smaller_zone_if_same_distance(self):
        """Test zone size preferences."""
        latitude = 32.880600
        longitude = -117.237561
        assert setup.setup_component(self.hass, zone.DOMAIN, {
            'zone': [
                {
                    'name': 'Small Zone',
                    'latitude': latitude,
                    'longitude': longitude,
                    'radius': 250,
                },
                {
                    'name': 'Big Zone',
                    'latitude': latitude,
                    'longitude': longitude,
                    'radius': 500,
                },
            ]
        })

        active = zone.zone.active_zone(self.hass, latitude, longitude)
        assert 'zone.small_zone' == active.entity_id

    def test_active_zone_prefers_smaller_zone_if_same_distance_2(self):
        """Test zone size preferences."""
        latitude = 32.880600
        longitude = -117.237561
        assert setup.setup_component(self.hass, zone.DOMAIN, {
            'zone': [
                {
                    'name': 'Smallest Zone',
                    'latitude': latitude,
                    'longitude': longitude,
                    'radius': 50,
                },
            ]
        })

        active = zone.zone.active_zone(self.hass, latitude, longitude)
        assert 'zone.smallest_zone' == active.entity_id

    def test_in_zone_works_for_passive_zones(self):
        """Test working in passive zones."""
        latitude = 32.880600
        longitude = -117.237561
        assert setup.setup_component(self.hass, zone.DOMAIN, {
            'zone': [
                {
                    'name': 'Passive Zone',
                    'latitude': latitude,
                    'longitude': longitude,
                    'radius': 250,
                    'passive': True
                },
            ]
        })

        assert zone.zone.in_zone(self.hass.states.get('zone.passive_zone'),
                                 latitude, longitude)
