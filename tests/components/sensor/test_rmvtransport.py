"""The tests for the rmvtransport platform."""
import unittest
from unittest.mock import patch
import datetime

from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant

VALID_CONFIG_MINIMAL = {'sensor': {'platform': 'rmvtransport',
                                   'next_departure': [{'station': '3000010'}]}}

VALID_CONFIG_NAME = {'sensor': {
    'platform': 'rmvtransport',
    'next_departure': [
        {
            'station': '3000010',
            'name': 'My Station',
        }
        ]}}

VALID_CONFIG_MISC = {'sensor': {
    'platform': 'rmvtransport',
    'next_departure': [
        {
            'station': '3000010',
            'lines': [21, 'S8'],
            'max_journeys': 2,
            'time_offset': 10
        }
        ]}}

VALID_CONFIG_DEST = {'sensor': {
    'platform': 'rmvtransport',
    'next_departure': [
        {
            'station': '3000010',
            'destinations': ['Frankfurt (Main) Flughafen Regionalbahnhof',
                             'Frankfurt (Main) Stadion']
        }
        ]}}


def get_departuresMock(stationId, maxJourneys,
                       products):  # pylint: disable=invalid-name
    """Mock rmvtransport departures loading."""
    data = {'station': 'Frankfurt (Main) Hauptbahnhof',
            'stationId': '3000010', 'filter': '11111111111', 'journeys': [
                {'product': 'Tram', 'number': 12, 'trainId': '1123456',
                 'direction': 'Frankfurt (Main) Hugo-Junkers-Straße/Schleife',
                 'departure_time': datetime.datetime(2018, 8, 6, 14, 21),
                 'minutes': 7, 'delay': 3, 'stops': [
                     'Frankfurt (Main) Willy-Brandt-Platz',
                     'Frankfurt (Main) Römer/Paulskirche',
                     'Frankfurt (Main) Börneplatz',
                     'Frankfurt (Main) Konstablerwache',
                     'Frankfurt (Main) Bornheim Mitte',
                     'Frankfurt (Main) Saalburg-/Wittelsbacherallee',
                     'Frankfurt (Main) Eissporthalle/Festplatz',
                     'Frankfurt (Main) Hugo-Junkers-Straße/Schleife'],
                 'info': None, 'info_long': None,
                 'icon': 'https://products/32_pic.png'},
                {'product': 'Bus', 'number': 21, 'trainId': '1234567',
                 'direction': 'Frankfurt (Main) Hugo-Junkers-Straße/Schleife',
                 'departure_time': datetime.datetime(2018, 8, 6, 14, 22),
                 'minutes': 8, 'delay': 1, 'stops': [
                     'Frankfurt (Main) Weser-/Münchener Straße',
                     'Frankfurt (Main) Hugo-Junkers-Straße/Schleife'],
                 'info': None, 'info_long': None,
                 'icon': 'https://products/32_pic.png'},
                {'product': 'Bus', 'number': 12, 'trainId': '1234568',
                 'direction': 'Frankfurt (Main) Hugo-Junkers-Straße/Schleife',
                 'departure_time': datetime.datetime(2018, 8, 6, 14, 25),
                 'minutes': 11, 'delay': 1, 'stops': [
                     'Frankfurt (Main) Stadion'],
                 'info': None, 'info_long': None,
                 'icon': 'https://products/32_pic.png'},
                {'product': 'Bus', 'number': 21, 'trainId': '1234569',
                 'direction': 'Frankfurt (Main) Hugo-Junkers-Straße/Schleife',
                 'departure_time': datetime.datetime(2018, 8, 6, 14, 25),
                 'minutes': 11, 'delay': 1, 'stops': [],
                 'info': None, 'info_long': None,
                 'icon': 'https://products/32_pic.png'},
                {'product': 'Bus', 'number': 12, 'trainId': '1234570',
                 'direction': 'Frankfurt (Main) Hugo-Junkers-Straße/Schleife',
                 'departure_time': datetime.datetime(2018, 8, 6, 14, 25),
                 'minutes': 11, 'delay': 1, 'stops': [],
                 'info': None, 'info_long': None,
                 'icon': 'https://products/32_pic.png'},
                {'product': 'Bus', 'number': 21, 'trainId': '1234571',
                 'direction': 'Frankfurt (Main) Hugo-Junkers-Straße/Schleife',
                 'departure_time': datetime.datetime(2018, 8, 6, 14, 25),
                 'minutes': 11, 'delay': 1, 'stops': [],
                 'info': None, 'info_long': None,
                 'icon': 'https://products/32_pic.png'}
                ]}
    return data


def get_errDeparturesMock(stationId, maxJourneys,
                          products):  # pylint: disable=invalid-name
    """Mock rmvtransport departures erroneous loading."""
    raise ValueError


class TestRMVtransportSensor(unittest.TestCase):
    """Test the rmvtransport sensor."""

    def setUp(self):
        """Set up things to run when tests begin."""
        self.hass = get_test_home_assistant()
        self.config = VALID_CONFIG_MINIMAL
        self.reference = {}
        self.entities = []

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @patch('RMVtransport.RMVtransport.get_departures',
           side_effect=get_departuresMock)
    def test_rmvtransport_min_config(self, mock_get_departures):
        """Test minimal rmvtransport configuration."""
        assert setup_component(self.hass, 'sensor', VALID_CONFIG_MINIMAL)
        state = self.hass.states.get('sensor.frankfurt_main_hauptbahnhof')
        self.assertEqual(state.state, '7')
        self.assertEqual(state.attributes['departure_time'],
                         datetime.datetime(2018, 8, 6, 14, 21))
        self.assertEqual(state.attributes['direction'],
                         'Frankfurt (Main) Hugo-Junkers-Straße/Schleife')
        self.assertEqual(state.attributes['product'], 'Tram')
        self.assertEqual(state.attributes['line'], 12)
        self.assertEqual(state.attributes['icon'], 'mdi:tram')
        self.assertEqual(state.attributes['friendly_name'],
                         'Frankfurt (Main) Hauptbahnhof')

    @patch('RMVtransport.RMVtransport.get_departures',
           side_effect=get_departuresMock)
    def test_rmvtransport_name_config(self, mock_get_departures):
        """Test custom name configuration."""
        assert setup_component(self.hass, 'sensor', VALID_CONFIG_NAME)
        state = self.hass.states.get('sensor.my_station')
        self.assertEqual(state.attributes['friendly_name'], 'My Station')

    @patch('RMVtransport.RMVtransport.get_departures',
           side_effect=get_errDeparturesMock)
    def test_rmvtransport_err_config(self, mock_get_departures):
        """Test erroneous rmvtransport configuration."""
        assert setup_component(self.hass, 'sensor', VALID_CONFIG_MINIMAL)

    @patch('RMVtransport.RMVtransport.get_departures',
           side_effect=get_departuresMock)
    def test_rmvtransport_misc_config(self, mock_get_departures):
        """Test misc configuration."""
        assert setup_component(self.hass, 'sensor', VALID_CONFIG_MISC)
        state = self.hass.states.get('sensor.frankfurt_main_hauptbahnhof')
        self.assertEqual(state.attributes['friendly_name'],
                         'Frankfurt (Main) Hauptbahnhof')
        self.assertEqual(state.attributes['line'], 21)

    @patch('RMVtransport.RMVtransport.get_departures',
           side_effect=get_departuresMock)
    def test_rmvtransport_dest_config(self, mock_get_departures):
        """Test misc configuration."""
        assert setup_component(self.hass, 'sensor', VALID_CONFIG_DEST)
        state = self.hass.states.get('sensor.frankfurt_main_hauptbahnhof')
        self.assertEqual(state.state, '11')
        self.assertEqual(state.attributes['direction'],
                         'Frankfurt (Main) Hugo-Junkers-Straße/Schleife')
        self.assertEqual(state.attributes['line'], 12)
        self.assertEqual(state.attributes['minutes'], 11)
        self.assertEqual(state.attributes['departure_time'],
                         datetime.datetime(2018, 8, 6, 14, 25))
