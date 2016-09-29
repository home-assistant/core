"""The tests for the device tracker component."""
# pylint: disable=protected-access,too-many-public-methods
import logging
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta
import os

from homeassistant.bootstrap import setup_component
from homeassistant.loader import get_component
import homeassistant.util.dt as dt_util
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_ENTITY_PICTURE, ATTR_FRIENDLY_NAME, ATTR_HIDDEN,
    STATE_HOME, STATE_NOT_HOME, CONF_PLATFORM)
import homeassistant.components.device_tracker as device_tracker
from homeassistant.exceptions import HomeAssistantError

from tests.common import (
    get_test_home_assistant, fire_time_changed, fire_service_discovered,
    patch_yaml_files)

TEST_PLATFORM = {device_tracker.DOMAIN: {CONF_PLATFORM: 'test'}}

_LOGGER = logging.getLogger(__name__)


class TestComponentsDeviceTracker(unittest.TestCase):
    """Test the Device tracker."""

    hass = None  # HomeAssistant
    yaml_devices = None  # type: str

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.yaml_devices = self.hass.config.path(device_tracker.YAML_DEVICES)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        try:
            os.remove(self.yaml_devices)
        except FileNotFoundError:
            pass

        self.hass.stop()

    def test_is_on(self):
        """Test is_on method."""
        entity_id = device_tracker.ENTITY_ID_FORMAT.format('test')

        self.hass.states.set(entity_id, STATE_HOME)

        self.assertTrue(device_tracker.is_on(self.hass, entity_id))

        self.hass.states.set(entity_id, STATE_NOT_HOME)

        self.assertFalse(device_tracker.is_on(self.hass, entity_id))

    def test_reading_broken_yaml_config(self):  # pylint: disable=no-self-use
        """Test when known devices contains invalid data."""
        files = {'empty.yaml': '',
                 'bad.yaml': '100',
                 'ok.yaml': 'my_device:\n  name: Device'}
        with patch_yaml_files(files):
            # File is empty
            assert device_tracker.load_config('empty.yaml', None, False) == []
            # File contains a non-dict format
            assert device_tracker.load_config('bad.yaml', None, False) == []
            # A file that works fine
            assert len(device_tracker.load_config('ok.yaml', None, False)) == 1

    def test_reading_yaml_config(self):
        """Test the rendering of the YAML configuration."""
        dev_id = 'test'
        device = device_tracker.Device(
            self.hass, timedelta(seconds=180), True, dev_id,
            'AB:CD:EF:GH:IJ', 'Test name', picture='http://test.picture',
            away_hide=True)
        device_tracker.update_config(self.yaml_devices, dev_id, device)
        self.assertTrue(setup_component(self.hass, device_tracker.DOMAIN,
                                        TEST_PLATFORM))
        config = device_tracker.load_config(self.yaml_devices, self.hass,
                                            device.consider_home)[0]
        self.assertEqual(device.dev_id, config.dev_id)
        self.assertEqual(device.track, config.track)
        self.assertEqual(device.mac, config.mac)
        self.assertEqual(device.config_picture, config.config_picture)
        self.assertEqual(device.away_hide, config.away_hide)
        self.assertEqual(device.consider_home, config.consider_home)

    @patch('homeassistant.components.device_tracker._LOGGER.warning')
    def test_track_with_duplicate_mac_dev_id(self, mock_warning):  \
            # pylint: disable=invalid-name
        """Test adding duplicate MACs or device IDs to DeviceTracker."""
        devices = [
            device_tracker.Device(self.hass, True, True, 'my_device', 'AB:01',
                                  'My device', None, None, False),
            device_tracker.Device(self.hass, True, True, 'your_device',
                                  'AB:01', 'Your device', None, None, False)]
        device_tracker.DeviceTracker(self.hass, False, True, devices)
        _LOGGER.debug(mock_warning.call_args_list)
        assert mock_warning.call_count == 1, \
            "The only warning call should be duplicates (check DEBUG)"
        args, _ = mock_warning.call_args
        assert 'Duplicate device MAC' in args[0], \
            'Duplicate MAC warning expected'

        mock_warning.reset_mock()
        devices = [
            device_tracker.Device(self.hass, True, True, 'my_device',
                                  'AB:01', 'My device', None, None, False),
            device_tracker.Device(self.hass, True, True, 'my_device',
                                  None, 'Your device', None, None, False)]
        device_tracker.DeviceTracker(self.hass, False, True, devices)

        _LOGGER.debug(mock_warning.call_args_list)
        assert mock_warning.call_count == 1, \
            "The only warning call should be duplicates (check DEBUG)"
        args, _ = mock_warning.call_args
        assert 'Duplicate device IDs' in args[0], \
            'Duplicate device IDs warning expected'

    def test_setup_without_yaml_file(self):
        """Test with no YAML file."""
        self.assertTrue(setup_component(self.hass, device_tracker.DOMAIN,
                                        TEST_PLATFORM))

    def test_adding_unknown_device_to_config(self): \
            # pylint: disable=invalid-name
        """Test the adding of unknown devices to configuration file."""
        scanner = get_component('device_tracker.test').SCANNER
        scanner.reset()
        scanner.come_home('DEV1')

        self.assertTrue(setup_component(self.hass, device_tracker.DOMAIN, {
            device_tracker.DOMAIN: {CONF_PLATFORM: 'test'}}))
        config = device_tracker.load_config(self.yaml_devices, self.hass,
                                            timedelta(seconds=0))
        assert len(config) == 1
        assert config[0].dev_id == 'dev1'
        assert config[0].track

    def test_gravatar(self):
        """Test the Gravatar generation."""
        dev_id = 'test'
        device = device_tracker.Device(
            self.hass, timedelta(seconds=180), True, dev_id,
            'AB:CD:EF:GH:IJ', 'Test name', gravatar='test@example.com')
        gravatar_url = ("https://www.gravatar.com/avatar/"
                        "55502f40dc8b7c769880b10874abc9d0.jpg?s=80&d=wavatar")
        self.assertEqual(device.config_picture, gravatar_url)

    def test_gravatar_and_picture(self):
        """Test that Gravatar overrides picture."""
        dev_id = 'test'
        device = device_tracker.Device(
            self.hass, timedelta(seconds=180), True, dev_id,
            'AB:CD:EF:GH:IJ', 'Test name', picture='http://test.picture',
            gravatar='test@example.com')
        gravatar_url = ("https://www.gravatar.com/avatar/"
                        "55502f40dc8b7c769880b10874abc9d0.jpg?s=80&d=wavatar")
        self.assertEqual(device.config_picture, gravatar_url)

    def test_discovery(self):
        """Test discovery."""
        scanner = get_component('device_tracker.test').SCANNER

        with patch.dict(device_tracker.DISCOVERY_PLATFORMS, {'test': 'test'}):
            with patch.object(scanner, 'scan_devices') as mock_scan:
                self.assertTrue(setup_component(
                    self.hass, device_tracker.DOMAIN, TEST_PLATFORM))
                fire_service_discovered(self.hass, 'test', {})
                self.assertTrue(mock_scan.called)

    def test_update_stale(self):
        """Test stalled update."""
        scanner = get_component('device_tracker.test').SCANNER
        scanner.reset()
        scanner.come_home('DEV1')

        register_time = datetime(2015, 9, 15, 23, tzinfo=dt_util.UTC)
        scan_time = datetime(2015, 9, 15, 23, 1, tzinfo=dt_util.UTC)

        with patch('homeassistant.components.device_tracker.dt_util.utcnow',
                   return_value=register_time):
            self.assertTrue(setup_component(self.hass, device_tracker.DOMAIN, {
                device_tracker.DOMAIN: {
                    CONF_PLATFORM: 'test',
                    device_tracker.CONF_CONSIDER_HOME: 59,
                }}))

        self.assertEqual(STATE_HOME,
                         self.hass.states.get('device_tracker.dev1').state)

        scanner.leave_home('DEV1')

        with patch('homeassistant.components.device_tracker.dt_util.utcnow',
                   return_value=scan_time):
            fire_time_changed(self.hass, scan_time)
            self.hass.block_till_done()

        self.assertEqual(STATE_NOT_HOME,
                         self.hass.states.get('device_tracker.dev1').state)

    def test_entity_attributes(self):
        """Test the entity attributes."""
        dev_id = 'test_entity'
        entity_id = device_tracker.ENTITY_ID_FORMAT.format(dev_id)
        friendly_name = 'Paulus'
        picture = 'http://placehold.it/200x200'

        device = device_tracker.Device(
            self.hass, timedelta(seconds=180), True, dev_id, None,
            friendly_name, picture, away_hide=True)
        device_tracker.update_config(self.yaml_devices, dev_id, device)

        self.assertTrue(setup_component(self.hass, device_tracker.DOMAIN,
                                        TEST_PLATFORM))

        attrs = self.hass.states.get(entity_id).attributes

        self.assertEqual(friendly_name, attrs.get(ATTR_FRIENDLY_NAME))
        self.assertEqual(picture, attrs.get(ATTR_ENTITY_PICTURE))

    def test_device_hidden(self):
        """Test hidden devices."""
        dev_id = 'test_entity'
        entity_id = device_tracker.ENTITY_ID_FORMAT.format(dev_id)
        device = device_tracker.Device(
            self.hass, timedelta(seconds=180), True, dev_id, None,
            away_hide=True)
        device_tracker.update_config(self.yaml_devices, dev_id, device)

        scanner = get_component('device_tracker.test').SCANNER
        scanner.reset()

        self.assertTrue(setup_component(self.hass, device_tracker.DOMAIN,
                                        TEST_PLATFORM))

        self.assertTrue(self.hass.states.get(entity_id)
                        .attributes.get(ATTR_HIDDEN))

    def test_group_all_devices(self):
        """Test grouping of devices."""
        dev_id = 'test_entity'
        entity_id = device_tracker.ENTITY_ID_FORMAT.format(dev_id)
        device = device_tracker.Device(
            self.hass, timedelta(seconds=180), True, dev_id, None,
            away_hide=True)
        device_tracker.update_config(self.yaml_devices, dev_id, device)

        scanner = get_component('device_tracker.test').SCANNER
        scanner.reset()

        self.assertTrue(setup_component(self.hass, device_tracker.DOMAIN,
                                        TEST_PLATFORM))

        state = self.hass.states.get(device_tracker.ENTITY_ID_ALL_DEVICES)
        self.assertIsNotNone(state)
        self.assertEqual(STATE_NOT_HOME, state.state)
        self.assertSequenceEqual((entity_id,),
                                 state.attributes.get(ATTR_ENTITY_ID))

    @patch('homeassistant.components.device_tracker.DeviceTracker.see')
    def test_see_service(self, mock_see):
        """Test the see service with a unicode dev_id and NO MAC."""
        self.assertTrue(setup_component(self.hass, device_tracker.DOMAIN,
                                        TEST_PLATFORM))
        params = {
            'dev_id': 'some_device',
            'host_name': 'example.com',
            'location_name': 'Work',
            'gps': [.3, .8]
        }
        device_tracker.see(self.hass, **params)
        self.hass.block_till_done()
        assert mock_see.call_count == 1
        mock_see.assert_called_once_with(**params)

        mock_see.reset_mock()
        params['dev_id'] += chr(233)  # e' acute accent from icloud

        device_tracker.see(self.hass, **params)
        self.hass.block_till_done()
        assert mock_see.call_count == 1
        mock_see.assert_called_once_with(**params)

    def test_not_write_duplicate_yaml_keys(self): \
            # pylint: disable=invalid-name
        """Test that the device tracker will not generate invalid YAML."""
        self.assertTrue(setup_component(self.hass, device_tracker.DOMAIN,
                                        TEST_PLATFORM))

        device_tracker.see(self.hass, 'mac_1', host_name='hello')
        device_tracker.see(self.hass, 'mac_2', host_name='hello')

        self.hass.block_till_done()

        config = device_tracker.load_config(self.yaml_devices, self.hass,
                                            timedelta(seconds=0))
        assert len(config) == 2

    def test_not_allow_invalid_dev_id(self):  # pylint: disable=invalid-name
        """Test that the device tracker will not allow invalid dev ids."""
        self.assertTrue(setup_component(self.hass, device_tracker.DOMAIN,
                                        TEST_PLATFORM))

        device_tracker.see(self.hass, dev_id='hello-world')

        config = device_tracker.load_config(self.yaml_devices, self.hass,
                                            timedelta(seconds=0))
        assert len(config) == 0

    @patch('homeassistant.components.device_tracker._LOGGER.warning')
    def test_see_failures(self, mock_warning):
        """Test that the device tracker see failures."""
        tracker = device_tracker.DeviceTracker(
            self.hass, timedelta(seconds=60), 0, [])

        # MAC is not a string (but added)
        tracker.see(mac=567, host_name="Number MAC")

        # No device id or MAC(not added)
        with self.assertRaises(HomeAssistantError):
            tracker.see()
        assert mock_warning.call_count == 0

        # Ignore gps on invalid GPS (both added & warnings)
        tracker.see(mac='mac_1_bad_gps', gps=1)
        tracker.see(mac='mac_2_bad_gps', gps=[1])
        tracker.see(mac='mac_3_bad_gps', gps='gps')
        config = device_tracker.load_config(self.yaml_devices, self.hass,
                                            timedelta(seconds=0))
        assert mock_warning.call_count == 3

        assert len(config) == 4

    @patch('homeassistant.components.device_tracker.log_exception')
    def test_config_failure(self, mock_ex):
        """Test that the device tracker see failures."""
        assert not setup_component(self.hass, device_tracker.DOMAIN,
                                   {device_tracker.DOMAIN: {
                                    device_tracker.CONF_CONSIDER_HOME: -1}})
