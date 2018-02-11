"""Philips Hue lights platform tests."""

import logging
import unittest
import unittest.mock as mock
from unittest.mock import call, MagicMock, patch

from homeassistant.components import hue
import homeassistant.components.light.hue as hue_light

from tests.common import get_test_home_assistant, MockDependency

_LOGGER = logging.getLogger(__name__)

HUE_LIGHT_NS = 'homeassistant.components.light.hue.'


class TestSetup(unittest.TestCase):
    """Test the Hue light platform."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.skip_teardown_stop = False

    def tearDown(self):
        """Stop everything that was started."""
        if not self.skip_teardown_stop:
            self.hass.stop()

    def setup_mocks_for_update_lights(self):
        """Set up all mocks for update_lights tests."""
        self.mock_bridge = MagicMock()
        self.mock_bridge.bridge_id = 'bridge-id'
        self.mock_bridge.allow_hue_groups = False
        self.mock_api = MagicMock()
        self.mock_bridge.get_api.return_value = self.mock_api
        self.mock_add_devices = MagicMock()

    def setup_mocks_for_process_lights(self):
        """Set up all mocks for process_lights tests."""
        self.mock_bridge = self.create_mock_bridge('host')
        self.mock_api = MagicMock()
        self.mock_api.get.return_value = {}
        self.mock_bridge.get_api.return_value = self.mock_api

    def setup_mocks_for_process_groups(self):
        """Set up all mocks for process_groups tests."""
        self.mock_bridge = self.create_mock_bridge('host')
        self.mock_bridge.get_group.return_value = {
            'name': 'Group 0', 'state': {'any_on': True}}

        self.mock_api = MagicMock()
        self.mock_api.get.return_value = {}
        self.mock_bridge.get_api.return_value = self.mock_api

    def create_mock_bridge(self, host, allow_hue_groups=True):
        """Return a mock HueBridge with reasonable defaults."""
        mock_bridge = MagicMock()
        mock_bridge.bridge_id = 'bridge-id'
        mock_bridge.host = host
        mock_bridge.allow_hue_groups = allow_hue_groups
        mock_bridge.lights = {}
        mock_bridge.lightgroups = {}
        return mock_bridge

    def create_mock_lights(self, lights):
        """Return a dict suitable for mocking api.get('lights')."""
        mock_bridge_lights = lights

        for info in mock_bridge_lights.values():
            if 'state' not in info:
                info['state'] = {'on': False}

        return mock_bridge_lights

    def build_mock_light(self, bridge, light_id, name):
        """Return a mock HueLight."""
        light = MagicMock()
        light.bridge = bridge
        light.light_id = light_id
        light.name = name
        return light

    def test_setup_platform_no_discovery_info(self):
        """Test setup_platform without discovery info."""
        self.hass.data[hue.DOMAIN] = {}
        mock_add_devices = MagicMock()

        hue_light.setup_platform(self.hass, {}, mock_add_devices)

        mock_add_devices.assert_not_called()

    def test_setup_platform_no_bridge_id(self):
        """Test setup_platform without a bridge."""
        self.hass.data[hue.DOMAIN] = {}
        mock_add_devices = MagicMock()

        hue_light.setup_platform(self.hass, {}, mock_add_devices, {})

        mock_add_devices.assert_not_called()

    def test_setup_platform_one_bridge(self):
        """Test setup_platform with one bridge."""
        mock_bridge = MagicMock()
        self.hass.data[hue.DOMAIN] = {'10.0.0.1': mock_bridge}
        mock_add_devices = MagicMock()

        with patch(HUE_LIGHT_NS + 'unthrottled_update_lights') \
                as mock_update_lights:
            hue_light.setup_platform(
                self.hass, {}, mock_add_devices,
                {'bridge_id': '10.0.0.1'})
            mock_update_lights.assert_called_once_with(
                self.hass, mock_bridge, mock_add_devices)

    def test_setup_platform_multiple_bridges(self):
        """Test setup_platform wuth multiple bridges."""
        mock_bridge = MagicMock()
        mock_bridge2 = MagicMock()
        self.hass.data[hue.DOMAIN] = {
            '10.0.0.1': mock_bridge,
            '192.168.0.10': mock_bridge2,
        }
        mock_add_devices = MagicMock()

        with patch(HUE_LIGHT_NS + 'unthrottled_update_lights') \
                as mock_update_lights:
            hue_light.setup_platform(
                self.hass, {}, mock_add_devices,
                {'bridge_id': '10.0.0.1'})
            hue_light.setup_platform(
                self.hass, {}, mock_add_devices,
                {'bridge_id': '192.168.0.10'})

            mock_update_lights.assert_has_calls([
                call(self.hass, mock_bridge, mock_add_devices),
                call(self.hass, mock_bridge2, mock_add_devices),
            ])

    @MockDependency('phue')
    def test_update_lights_with_no_lights(self, mock_phue):
        """Test the update_lights function when no lights are found."""
        self.setup_mocks_for_update_lights()

        with patch(HUE_LIGHT_NS + 'process_lights', return_value=[]) \
                as mock_process_lights:
            with patch(HUE_LIGHT_NS + 'process_groups', return_value=[]) \
                    as mock_process_groups:
                with patch.object(self.hass.helpers.dispatcher,
                                  'dispatcher_send') as dispatcher_send:
                    hue_light.unthrottled_update_lights(
                        self.hass, self.mock_bridge, self.mock_add_devices)

                    mock_process_lights.assert_called_once_with(
                        self.hass, self.mock_api, self.mock_bridge, mock.ANY)
                    mock_process_groups.assert_not_called()
                    self.mock_add_devices.assert_not_called()
                    dispatcher_send.assert_not_called()

    @MockDependency('phue')
    def test_update_lights_with_some_lights(self, mock_phue):
        """Test the update_lights function with some lights."""
        self.setup_mocks_for_update_lights()
        mock_lights = [
            self.build_mock_light(self.mock_bridge, 42, 'some'),
            self.build_mock_light(self.mock_bridge, 84, 'light'),
        ]

        with patch(HUE_LIGHT_NS + 'process_lights',
                   return_value=mock_lights) as mock_process_lights:
            with patch(HUE_LIGHT_NS + 'process_groups', return_value=[]) \
                    as mock_process_groups:
                with patch.object(self.hass.helpers.dispatcher,
                                  'dispatcher_send') as dispatcher_send:
                    hue_light.unthrottled_update_lights(
                        self.hass, self.mock_bridge, self.mock_add_devices)

                    mock_process_lights.assert_called_once_with(
                        self.hass, self.mock_api, self.mock_bridge, mock.ANY)
                    mock_process_groups.assert_not_called()
                    self.mock_add_devices.assert_called_once_with(
                        mock_lights)
                    dispatcher_send.assert_not_called()

    @MockDependency('phue')
    def test_update_lights_no_groups(self, mock_phue):
        """Test the update_lights function when no groups are found."""
        self.setup_mocks_for_update_lights()
        self.mock_bridge.allow_hue_groups = True
        mock_lights = [
            self.build_mock_light(self.mock_bridge, 42, 'some'),
            self.build_mock_light(self.mock_bridge, 84, 'light'),
        ]

        with patch(HUE_LIGHT_NS + 'process_lights',
                   return_value=mock_lights) as mock_process_lights:
            with patch(HUE_LIGHT_NS + 'process_groups', return_value=[]) \
                    as mock_process_groups:
                with patch.object(self.hass.helpers.dispatcher,
                                  'dispatcher_send') as dispatcher_send:
                    hue_light.unthrottled_update_lights(
                        self.hass, self.mock_bridge, self.mock_add_devices)

                    mock_process_lights.assert_called_once_with(
                        self.hass, self.mock_api, self.mock_bridge, mock.ANY)
                    mock_process_groups.assert_called_once_with(
                        self.hass, self.mock_api, self.mock_bridge, mock.ANY)
                    self.mock_add_devices.assert_called_once_with(
                        mock_lights)
                    dispatcher_send.assert_not_called()

    @MockDependency('phue')
    def test_update_lights_with_lights_and_groups(self, mock_phue):
        """Test the update_lights function with both lights and groups."""
        self.setup_mocks_for_update_lights()
        self.mock_bridge.allow_hue_groups = True
        mock_lights = [
            self.build_mock_light(self.mock_bridge, 42, 'some'),
            self.build_mock_light(self.mock_bridge, 84, 'light'),
        ]
        mock_groups = [
            self.build_mock_light(self.mock_bridge, 15, 'and'),
            self.build_mock_light(self.mock_bridge, 72, 'groups'),
        ]

        with patch(HUE_LIGHT_NS + 'process_lights',
                   return_value=mock_lights) as mock_process_lights:
            with patch(HUE_LIGHT_NS + 'process_groups',
                       return_value=mock_groups) as mock_process_groups:
                with patch.object(self.hass.helpers.dispatcher,
                                  'dispatcher_send') as dispatcher_send:
                    hue_light.unthrottled_update_lights(
                        self.hass, self.mock_bridge, self.mock_add_devices)

                    mock_process_lights.assert_called_once_with(
                        self.hass, self.mock_api, self.mock_bridge, mock.ANY)
                    mock_process_groups.assert_called_once_with(
                        self.hass, self.mock_api, self.mock_bridge, mock.ANY)
                    # note that mock_lights has been modified in place and
                    # now contains both lights and groups
                    self.mock_add_devices.assert_called_once_with(
                        mock_lights)
                    dispatcher_send.assert_not_called()

    @MockDependency('phue')
    def test_update_lights_with_two_bridges(self, mock_phue):
        """Test the update_lights function with two bridges."""
        self.setup_mocks_for_update_lights()

        mock_bridge_one = self.create_mock_bridge('one', False)
        mock_bridge_one_lights = self.create_mock_lights(
            {1: {'name': 'b1l1'}, 2: {'name': 'b1l2'}})

        mock_bridge_two = self.create_mock_bridge('two', False)
        mock_bridge_two_lights = self.create_mock_lights(
            {1: {'name': 'b2l1'}, 3: {'name': 'b2l3'}})

        with patch('homeassistant.components.light.hue.HueLight.'
                   'schedule_update_ha_state'):
            mock_api = MagicMock()
            mock_api.get.return_value = mock_bridge_one_lights
            with patch.object(mock_bridge_one, 'get_api',
                              return_value=mock_api):
                hue_light.unthrottled_update_lights(
                    self.hass, mock_bridge_one, self.mock_add_devices)

            mock_api = MagicMock()
            mock_api.get.return_value = mock_bridge_two_lights
            with patch.object(mock_bridge_two, 'get_api',
                              return_value=mock_api):
                hue_light.unthrottled_update_lights(
                    self.hass, mock_bridge_two, self.mock_add_devices)

        self.assertEqual(sorted(mock_bridge_one.lights.keys()), [1, 2])
        self.assertEqual(sorted(mock_bridge_two.lights.keys()), [1, 3])

        self.assertEqual(len(self.mock_add_devices.mock_calls), 2)

        # first call
        name, args, kwargs = self.mock_add_devices.mock_calls[0]
        self.assertEqual(len(args), 1)
        self.assertEqual(len(kwargs), 0)

        # second call works the same
        name, args, kwargs = self.mock_add_devices.mock_calls[1]
        self.assertEqual(len(args), 1)
        self.assertEqual(len(kwargs), 0)

    def test_process_lights_api_error(self):
        """Test the process_lights function when the bridge errors out."""
        self.setup_mocks_for_process_lights()
        self.mock_api.get.return_value = None

        ret = hue_light.process_lights(
            self.hass, self.mock_api, self.mock_bridge, None)

        self.assertEqual([], ret)
        self.assertEqual(self.mock_bridge.lights, {})

    def test_process_lights_no_lights(self):
        """Test the process_lights function when bridge returns no lights."""
        self.setup_mocks_for_process_lights()

        with patch.object(self.hass.helpers.dispatcher, 'dispatcher_send') \
                as mock_dispatcher_send:
            ret = hue_light.process_lights(
                self.hass, self.mock_api, self.mock_bridge, None)

            self.assertEqual([], ret)
            mock_dispatcher_send.assert_not_called()
            self.assertEqual(self.mock_bridge.lights, {})

    @patch(HUE_LIGHT_NS + 'HueLight')
    def test_process_lights_some_lights(self, mock_hue_light):
        """Test the process_lights function with multiple groups."""
        self.setup_mocks_for_process_lights()
        self.mock_api.get.return_value = {
            1: {'state': 'on'}, 2: {'state': 'off'}}

        with patch.object(self.hass.helpers.dispatcher, 'dispatcher_send') \
                as mock_dispatcher_send:
            ret = hue_light.process_lights(
                self.hass, self.mock_api, self.mock_bridge, None)

            self.assertEqual(len(ret), 2)
            mock_hue_light.assert_has_calls([
                call(
                    1, {'state': 'on'}, self.mock_bridge, mock.ANY,
                    self.mock_bridge.allow_unreachable,
                    self.mock_bridge.allow_in_emulated_hue),
                call(
                    2, {'state': 'off'}, self.mock_bridge, mock.ANY,
                    self.mock_bridge.allow_unreachable,
                    self.mock_bridge.allow_in_emulated_hue),
            ])
            mock_dispatcher_send.assert_not_called()
            self.assertEqual(len(self.mock_bridge.lights), 2)

    @patch(HUE_LIGHT_NS + 'HueLight')
    def test_process_lights_new_light(self, mock_hue_light):
        """
        Test the process_lights function with new groups.

        Test what happens when we already have a light and a new one shows up.
        """
        self.setup_mocks_for_process_lights()
        self.mock_api.get.return_value = {
            1: {'state': 'on'}, 2: {'state': 'off'}}
        self.mock_bridge.lights = {
            1: self.build_mock_light(self.mock_bridge, 1, 'foo')}

        with patch.object(self.hass.helpers.dispatcher, 'dispatcher_send') \
                as mock_dispatcher_send:
            ret = hue_light.process_lights(
                self.hass, self.mock_api, self.mock_bridge, None)

            self.assertEqual(len(ret), 1)
            mock_hue_light.assert_has_calls([
                call(
                    2, {'state': 'off'}, self.mock_bridge, mock.ANY,
                    self.mock_bridge.allow_unreachable,
                    self.mock_bridge.allow_in_emulated_hue),
            ])
            mock_dispatcher_send.assert_called_once_with(
                'hue_light_callback_bridge-id_1')
            self.assertEqual(len(self.mock_bridge.lights), 2)

    def test_process_groups_api_error(self):
        """Test the process_groups function when the bridge errors out."""
        self.setup_mocks_for_process_groups()
        self.mock_api.get.return_value = None

        ret = hue_light.process_groups(
            self.hass, self.mock_api, self.mock_bridge, None)

        self.assertEqual([], ret)
        self.assertEqual(self.mock_bridge.lightgroups, {})

    def test_process_groups_no_state(self):
        """Test the process_groups function when bridge returns no status."""
        self.setup_mocks_for_process_groups()
        self.mock_bridge.get_group.return_value = {'name': 'Group 0'}

        with patch.object(self.hass.helpers.dispatcher, 'dispatcher_send') \
                as mock_dispatcher_send:
            ret = hue_light.process_groups(
                self.hass, self.mock_api, self.mock_bridge, None)

            self.assertEqual([], ret)
            mock_dispatcher_send.assert_not_called()
            self.assertEqual(self.mock_bridge.lightgroups, {})

    @patch(HUE_LIGHT_NS + 'HueLight')
    def test_process_groups_some_groups(self, mock_hue_light):
        """Test the process_groups function with multiple groups."""
        self.setup_mocks_for_process_groups()
        self.mock_api.get.return_value = {
            1: {'state': 'on'}, 2: {'state': 'off'}}

        with patch.object(self.hass.helpers.dispatcher, 'dispatcher_send') \
                as mock_dispatcher_send:
            ret = hue_light.process_groups(
                self.hass, self.mock_api, self.mock_bridge, None)

            self.assertEqual(len(ret), 2)
            mock_hue_light.assert_has_calls([
                call(
                    1, {'state': 'on'}, self.mock_bridge, mock.ANY,
                    self.mock_bridge.allow_unreachable,
                    self.mock_bridge.allow_in_emulated_hue, True),
                call(
                    2, {'state': 'off'}, self.mock_bridge, mock.ANY,
                    self.mock_bridge.allow_unreachable,
                    self.mock_bridge.allow_in_emulated_hue, True),
            ])
            mock_dispatcher_send.assert_not_called()
            self.assertEqual(len(self.mock_bridge.lightgroups), 2)

    @patch(HUE_LIGHT_NS + 'HueLight')
    def test_process_groups_new_group(self, mock_hue_light):
        """
        Test the process_groups function with new groups.

        Test what happens when we already have a light and a new one shows up.
        """
        self.setup_mocks_for_process_groups()
        self.mock_api.get.return_value = {
            1: {'state': 'on'}, 2: {'state': 'off'}}
        self.mock_bridge.lightgroups = {
                1: self.build_mock_light(self.mock_bridge, 1, 'foo')}

        with patch.object(self.hass.helpers.dispatcher, 'dispatcher_send') \
                as mock_dispatcher_send:
            ret = hue_light.process_groups(
                self.hass, self.mock_api, self.mock_bridge, None)

            self.assertEqual(len(ret), 1)
            mock_hue_light.assert_has_calls([
                call(
                    2, {'state': 'off'}, self.mock_bridge, mock.ANY,
                    self.mock_bridge.allow_unreachable,
                    self.mock_bridge.allow_in_emulated_hue, True),
            ])
            mock_dispatcher_send.assert_called_once_with(
                'hue_light_callback_bridge-id_1')
            self.assertEqual(len(self.mock_bridge.lightgroups), 2)


class TestHueLight(unittest.TestCase):
    """Test the HueLight class."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.skip_teardown_stop = False

        self.light_id = 42
        self.mock_info = MagicMock()
        self.mock_bridge = MagicMock()
        self.mock_update_lights = MagicMock()
        self.mock_allow_unreachable = MagicMock()
        self.mock_is_group = MagicMock()
        self.mock_allow_in_emulated_hue = MagicMock()
        self.mock_is_group = False

    def tearDown(self):
        """Stop everything that was started."""
        if not self.skip_teardown_stop:
            self.hass.stop()

    def buildLight(
            self, light_id=None, info=None, update_lights=None, is_group=None):
        """Helper to build a HueLight object with minimal fuss."""
        if 'state' not in info:
            on_key = 'any_on' if is_group is not None else 'on'
            info['state'] = {on_key: False}

        return hue_light.HueLight(
            light_id if light_id is not None else self.light_id,
            info if info is not None else self.mock_info,
            self.mock_bridge,
            (update_lights
             if update_lights is not None
             else self.mock_update_lights),
            self.mock_allow_unreachable, self.mock_allow_in_emulated_hue,
            is_group if is_group is not None else self.mock_is_group)

    def test_unique_id_for_light(self):
        """Test the unique_id method with lights."""
        light = self.buildLight(info={'uniqueid': 'foobar'})
        self.assertEqual('foobar', light.unique_id)

        light = self.buildLight(info={})
        self.assertIsNone(light.unique_id)

    def test_unique_id_for_group(self):
        """Test the unique_id method with groups."""
        light = self.buildLight(info={'uniqueid': 'foobar'}, is_group=True)
        self.assertEqual('foobar', light.unique_id)

        light = self.buildLight(info={}, is_group=True)
        self.assertIsNone(light.unique_id)
