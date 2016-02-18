"""
tests.components.device_tracker.test_init
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the device tracker compoments.
"""
# pylint: disable=protected-access,too-many-public-methods
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta
import os

from homeassistant.config import load_yaml_config_file
from homeassistant.loader import get_component
import homeassistant.util.dt as dt_util
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_ENTITY_PICTURE, ATTR_FRIENDLY_NAME, ATTR_HIDDEN,
    STATE_HOME, STATE_NOT_HOME, CONF_PLATFORM, DEVICE_DEFAULT_NAME)
import homeassistant.components.device_tracker as device_tracker

from tests.common import (
    get_test_home_assistant, fire_time_changed, fire_service_discovered)


class TestComponentsDeviceTracker(unittest.TestCase):
    """ Tests homeassistant.components.device_tracker module. """

    def setUp(self):  # pylint: disable=invalid-name
        """ Init needed objects. """
        self.hass = get_test_home_assistant()
        self.yaml_devices = self.hass.config.path(device_tracker.YAML_DEVICES)

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        try:
            os.remove(self.yaml_devices)
        except FileNotFoundError:
            pass

        self.hass.stop()

    def test_is_on(self):
        """ Test is_on method. """
        entity_id = device_tracker.ENTITY_ID_FORMAT.format('test')

        self.hass.states.set(entity_id, STATE_HOME)

        self.assertTrue(device_tracker.is_on(self.hass, entity_id))

        self.hass.states.set(entity_id, STATE_NOT_HOME)

        self.assertFalse(device_tracker.is_on(self.hass, entity_id))

    def test_migrating_config(self):
        csv_devices = self.hass.config.path(device_tracker.CSV_DEVICES)

        self.assertFalse(os.path.isfile(csv_devices))
        self.assertFalse(os.path.isfile(self.yaml_devices))

        person1 = {
            'mac': 'AB:CD:EF:GH:IJ:KL',
            'name': 'Paulus',
            'track': True,
            'picture': 'http://placehold.it/200x200',
        }
        person2 = {
            'mac': 'MN:OP:QR:ST:UV:WX:YZ',
            'name': '',
            'track': False,
            'picture': None,
        }

        try:
            with open(csv_devices, 'w') as fil:
                fil.write('device,name,track,picture\n')
                for pers in (person1, person2):
                    fil.write('{},{},{},{}\n'.format(
                        pers['mac'], pers['name'],
                        '1' if pers['track'] else '0', pers['picture'] or ''))

            self.assertTrue(device_tracker.setup(self.hass, {}))
            self.assertFalse(os.path.isfile(csv_devices))
            self.assertTrue(os.path.isfile(self.yaml_devices))

            yaml_config = load_yaml_config_file(self.yaml_devices)

            self.assertEqual(2, len(yaml_config))

            for pers, yaml_pers in zip(
                (person1, person2), sorted(yaml_config.values(),
                                           key=lambda pers: pers['mac'])):
                for key, value in pers.items():
                    if key == 'name' and value == '':
                        value = DEVICE_DEFAULT_NAME
                    self.assertEqual(value, yaml_pers.get(key))

        finally:
            try:
                os.remove(csv_devices)
            except FileNotFoundError:
                pass

    def test_reading_yaml_config(self):
        dev_id = 'test'
        device = device_tracker.Device(
            self.hass, timedelta(seconds=180), 0, True, dev_id,
            'AB:CD:EF:GH:IJ', 'Test name', 'http://test.picture', True)
        device_tracker.update_config(self.yaml_devices, dev_id, device)
        self.assertTrue(device_tracker.setup(self.hass, {}))
        config = device_tracker.load_config(self.yaml_devices, self.hass,
                                            device.consider_home, 0)[0]
        self.assertEqual(device.dev_id, config.dev_id)
        self.assertEqual(device.track, config.track)
        self.assertEqual(device.mac, config.mac)
        self.assertEqual(device.config_picture, config.config_picture)
        self.assertEqual(device.away_hide, config.away_hide)
        self.assertEqual(device.consider_home, config.consider_home)

    def test_setup_without_yaml_file(self):
        self.assertTrue(device_tracker.setup(self.hass, {}))

    def test_adding_unknown_device_to_config(self):
        scanner = get_component('device_tracker.test').SCANNER
        scanner.reset()
        scanner.come_home('DEV1')

        self.assertTrue(device_tracker.setup(self.hass, {
            device_tracker.DOMAIN: {CONF_PLATFORM: 'test'}}))
        config = device_tracker.load_config(self.yaml_devices, self.hass,
                                            timedelta(seconds=0), 0)
        assert len(config) == 1
        assert config[0].dev_id == 'dev1'
        assert config[0].track

    def test_discovery(self):
        scanner = get_component('device_tracker.test').SCANNER

        with patch.dict(device_tracker.DISCOVERY_PLATFORMS, {'test': 'test'}):
            with patch.object(scanner, 'scan_devices') as mock_scan:
                self.assertTrue(device_tracker.setup(self.hass, {
                    device_tracker.DOMAIN: {CONF_PLATFORM: 'test'}}))
                fire_service_discovered(self.hass, 'test', {})
                self.assertTrue(mock_scan.called)

    def test_update_stale(self):
        scanner = get_component('device_tracker.test').SCANNER
        scanner.reset()
        scanner.come_home('DEV1')

        register_time = datetime(2015, 9, 15, 23, tzinfo=dt_util.UTC)
        scan_time = datetime(2015, 9, 15, 23, 1, tzinfo=dt_util.UTC)

        with patch('homeassistant.components.device_tracker.dt_util.utcnow',
                   return_value=register_time):
            self.assertTrue(device_tracker.setup(self.hass, {
                'device_tracker': {
                    'platform': 'test',
                    'consider_home': 59,
                }}))

        self.assertEqual(STATE_HOME,
                         self.hass.states.get('device_tracker.dev1').state)

        scanner.leave_home('DEV1')

        with patch('homeassistant.components.device_tracker.dt_util.utcnow',
                   return_value=scan_time):
            fire_time_changed(self.hass, scan_time)
            self.hass.pool.block_till_done()

        self.assertEqual(STATE_NOT_HOME,
                         self.hass.states.get('device_tracker.dev1').state)

    def test_entity_attributes(self):
        dev_id = 'test_entity'
        entity_id = device_tracker.ENTITY_ID_FORMAT.format(dev_id)
        friendly_name = 'Paulus'
        picture = 'http://placehold.it/200x200'

        device = device_tracker.Device(
            self.hass, timedelta(seconds=180), 0, True, dev_id, None,
            friendly_name, picture, away_hide=True)
        device_tracker.update_config(self.yaml_devices, dev_id, device)

        self.assertTrue(device_tracker.setup(self.hass, {}))

        attrs = self.hass.states.get(entity_id).attributes

        self.assertEqual(friendly_name, attrs.get(ATTR_FRIENDLY_NAME))
        self.assertEqual(picture, attrs.get(ATTR_ENTITY_PICTURE))

    def test_device_hidden(self):
        dev_id = 'test_entity'
        entity_id = device_tracker.ENTITY_ID_FORMAT.format(dev_id)
        device = device_tracker.Device(
            self.hass, timedelta(seconds=180), 0, True, dev_id, None,
            away_hide=True)
        device_tracker.update_config(self.yaml_devices, dev_id, device)

        scanner = get_component('device_tracker.test').SCANNER
        scanner.reset()

        self.assertTrue(device_tracker.setup(self.hass, {
            device_tracker.DOMAIN: {CONF_PLATFORM: 'test'}}))

        self.assertTrue(self.hass.states.get(entity_id)
                            .attributes.get(ATTR_HIDDEN))

    def test_group_all_devices(self):
        dev_id = 'test_entity'
        entity_id = device_tracker.ENTITY_ID_FORMAT.format(dev_id)
        device = device_tracker.Device(
            self.hass, timedelta(seconds=180), 0, True, dev_id, None,
            away_hide=True)
        device_tracker.update_config(self.yaml_devices, dev_id, device)

        scanner = get_component('device_tracker.test').SCANNER
        scanner.reset()

        self.assertTrue(device_tracker.setup(self.hass, {
            device_tracker.DOMAIN: {CONF_PLATFORM: 'test'}}))

        state = self.hass.states.get(device_tracker.ENTITY_ID_ALL_DEVICES)
        self.assertIsNotNone(state)
        self.assertEqual(STATE_NOT_HOME, state.state)
        self.assertSequenceEqual((entity_id,),
                                 state.attributes.get(ATTR_ENTITY_ID))

    @patch('homeassistant.components.device_tracker.DeviceTracker.see')
    def test_see_service(self, mock_see):
        self.assertTrue(device_tracker.setup(self.hass, {}))
        mac = 'AB:CD:EF:GH'
        dev_id = 'some_device'
        host_name = 'example.com'
        location_name = 'Work'
        gps = [.3, .8]

        device_tracker.see(self.hass, mac, dev_id, host_name, location_name,
                           gps)

        self.hass.pool.block_till_done()

        mock_see.assert_called_once_with(
            mac=mac, dev_id=dev_id, host_name=host_name,
            location_name=location_name, gps=gps)
