"""Philips Hue lights platform tests."""

import logging
import unittest
import unittest.mock as mock
from unittest.mock import call, MagicMock, patch

from homeassistant.components import hue
import homeassistant.components.light.hue as hue_light

from tests.common import get_test_home_assistant, MockDependency

_LOGGER = logging.getLogger(__name__)


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
        self.mock_bridge.allow_hue_groups = False
        self.mock_api = MagicMock()
        self.mock_bridge.get_api.return_value = self.mock_api
        self.mock_bridge_type = MagicMock()
        self.mock_lights = []
        self.mock_groups = []
        self.mock_add_devices = MagicMock()
        hue_light.setup_data(self.hass)

    def setup_mocks_for_process_lights(self):
        """Set up all mocks for process_lights tests."""
        self.mock_bridge = MagicMock()
        self.mock_api = MagicMock()
        self.mock_api.get.return_value = {}
        self.mock_bridge.get_api.return_value = self.mock_api
        self.mock_bridge_type = MagicMock()
        hue_light.setup_data(self.hass)

    def setup_mocks_for_process_groups(self):
        """Set up all mocks for process_groups tests."""
        self.mock_bridge = MagicMock()
        self.mock_bridge.get_group.return_value = {
            'name': 'Group 0', 'state': {'any_on': True}}
        self.mock_api = MagicMock()
        self.mock_api.get.return_value = {}
        self.mock_bridge.get_api.return_value = self.mock_api
        self.mock_bridge_type = MagicMock()
        hue_light.setup_data(self.hass)

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

        with patch('homeassistant.components.light.hue.' +
                   'unthrottled_update_lights') as mock_update_lights:
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

        with patch('homeassistant.components.light.hue.' +
                   'unthrottled_update_lights') as mock_update_lights:
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

        with patch('homeassistant.components.light.hue.get_bridge_type',
                   return_value=self.mock_bridge_type):
            with patch('homeassistant.components.light.hue.process_lights',
                       return_value=[]) as mock_process_lights:
                with patch('homeassistant.components.light.hue.process_groups',
                           return_value=self.mock_groups) \
                        as mock_process_groups:
                    hue_light.unthrottled_update_lights(
                        self.hass, self.mock_bridge, self.mock_add_devices)

                    mock_process_lights.assert_called_once_with(
                        self.hass, self.mock_api, self.mock_bridge,
                        self.mock_bridge_type, mock.ANY)
                    mock_process_groups.assert_not_called()
                    self.mock_add_devices.assert_not_called()

    @MockDependency('phue')
    def test_update_lights_with_some_lights(self, mock_phue):
        """Test the update_lights function with some lights."""
        self.setup_mocks_for_update_lights()
        self.mock_lights = ['some', 'light']

        with patch('homeassistant.components.light.hue.get_bridge_type',
                   return_value=self.mock_bridge_type):
            with patch('homeassistant.components.light.hue.process_lights',
                       return_value=self.mock_lights) as mock_process_lights:
                with patch('homeassistant.components.light.hue.process_groups',
                           return_value=self.mock_groups) \
                        as mock_process_groups:
                    hue_light.unthrottled_update_lights(
                        self.hass, self.mock_bridge, self.mock_add_devices)

                    mock_process_lights.assert_called_once_with(
                        self.hass, self.mock_api, self.mock_bridge,
                        self.mock_bridge_type, mock.ANY)
                    mock_process_groups.assert_not_called()
                    self.mock_add_devices.assert_called_once_with(
                        self.mock_lights)

    @MockDependency('phue')
    def test_update_lights_no_groups(self, mock_phue):
        """Test the update_lights function when no groups are found."""
        self.setup_mocks_for_update_lights()
        self.mock_bridge.allow_hue_groups = True
        self.mock_lights = ['some', 'light']

        with patch('homeassistant.components.light.hue.get_bridge_type',
                   return_value=self.mock_bridge_type):
            with patch('homeassistant.components.light.hue.process_lights',
                       return_value=self.mock_lights) as mock_process_lights:
                with patch('homeassistant.components.light.hue.process_groups',
                           return_value=self.mock_groups) \
                        as mock_process_groups:
                    hue_light.unthrottled_update_lights(
                        self.hass, self.mock_bridge, self.mock_add_devices)

                    mock_process_lights.assert_called_once_with(
                        self.hass, self.mock_api, self.mock_bridge,
                        self.mock_bridge_type, mock.ANY)
                    mock_process_groups.assert_called_once_with(
                        self.hass, self.mock_api, self.mock_bridge,
                        self.mock_bridge_type, mock.ANY)
                    self.mock_add_devices.assert_called_once_with(
                        self.mock_lights)

    @MockDependency('phue')
    def test_update_lights_with_lights_and_groups(self, mock_phue):
        """Test the update_lights function with both lights and groups."""
        self.setup_mocks_for_update_lights()
        self.mock_bridge.allow_hue_groups = True
        self.mock_lights = ['some', 'light']
        self.mock_groups = ['and', 'groups']

        with patch('homeassistant.components.light.hue.get_bridge_type',
                   return_value=self.mock_bridge_type):
            with patch('homeassistant.components.light.hue.process_lights',
                       return_value=self.mock_lights) as mock_process_lights:
                with patch('homeassistant.components.light.hue.process_groups',
                           return_value=self.mock_groups) \
                        as mock_process_groups:
                    hue_light.unthrottled_update_lights(
                        self.hass, self.mock_bridge, self.mock_add_devices)

                    mock_process_lights.assert_called_once_with(
                        self.hass, self.mock_api, self.mock_bridge,
                        self.mock_bridge_type, mock.ANY)
                    mock_process_groups.assert_called_once_with(
                        self.hass, self.mock_api, self.mock_bridge,
                        self.mock_bridge_type, mock.ANY)
                    self.mock_add_devices.assert_called_once_with(
                        self.mock_lights)

    def test_process_lights_api_error(self):
        """Test the process_lights function when the bridge errors out."""
        self.setup_mocks_for_process_lights()
        self.mock_api.get.return_value = None

        ret = hue_light.process_lights(
            self.hass, self.mock_api, self.mock_bridge, self.mock_bridge_type,
            None)

        self.assertEquals([], ret)
        self.assertEquals(
            {},
            self.hass.data[hue_light.DATA_KEY][hue_light.DATA_LIGHTS])

    def test_process_lights_no_lights(self):
        """Test the process_lights function when bridge returns no lights."""
        self.setup_mocks_for_process_lights()

        ret = hue_light.process_lights(
            self.hass, self.mock_api, self.mock_bridge, self.mock_bridge_type,
            None)

        self.assertEquals([], ret)
        self.assertEquals(
            {},
            self.hass.data[hue_light.DATA_KEY][hue_light.DATA_LIGHTS])

    @patch('homeassistant.components.light.hue.HueLight')
    def test_process_lights_some_lights(self, mock_hue_light):
        """Test the process_lights function with multiple groups."""
        self.setup_mocks_for_process_lights()
        self.mock_api.get.return_value = {
            1: {'state': 'on'}, 2: {'state': 'off'}}

        ret = hue_light.process_lights(
            self.hass, self.mock_api, self.mock_bridge, self.mock_bridge_type,
            None)

        self.assertEquals(len(ret), 2)
        mock_hue_light.assert_has_calls([
            call(
                1, {'state': 'on'}, self.mock_bridge, mock.ANY,
                self.mock_bridge_type, self.mock_bridge.allow_unreachable,
                self.mock_bridge.allow_in_emulated_hue),
            call(
                2, {'state': 'off'}, self.mock_bridge, mock.ANY,
                self.mock_bridge_type, self.mock_bridge.allow_unreachable,
                self.mock_bridge.allow_in_emulated_hue),
        ])
        self.assertEquals(
            len(self.hass.data[hue_light.DATA_KEY][hue_light.DATA_LIGHTS]),
            2)

    @patch('homeassistant.components.light.hue.HueLight')
    def test_process_lights_new_light(self, mock_hue_light):
        """
        Test the process_lights function with new groups.

        Test what happens when we already have a light and a new one shows up.
        """
        self.setup_mocks_for_process_lights()
        self.mock_api.get.return_value = {
            1: {'state': 'on'}, 2: {'state': 'off'}}
        self.hass.data[
            hue_light.DATA_KEY][hue_light.DATA_LIGHTS][1] = MagicMock()

        ret = hue_light.process_lights(
            self.hass, self.mock_api, self.mock_bridge, self.mock_bridge_type,
            None)

        self.assertEquals(len(ret), 1)
        mock_hue_light.assert_has_calls([
            call(
                2, {'state': 'off'}, self.mock_bridge, mock.ANY,
                self.mock_bridge_type, self.mock_bridge.allow_unreachable,
                self.mock_bridge.allow_in_emulated_hue),
        ])
        self.hass.data[hue_light.DATA_KEY][hue_light.DATA_LIGHTS][
            1].schedule_update_ha_state.assert_called_once_with()
        self.assertEquals(
            len(self.hass.data[hue_light.DATA_KEY][hue_light.DATA_LIGHTS]),
            2)

    def test_process_groups_api_error(self):
        """Test the process_groups function when the bridge errors out."""
        self.setup_mocks_for_process_groups()
        self.mock_api.get.return_value = None

        ret = hue_light.process_groups(
            self.hass, self.mock_api, self.mock_bridge, self.mock_bridge_type,
            None)

        self.assertEquals([], ret)
        self.assertEquals(
            {},
            self.hass.data[hue_light.DATA_KEY][hue_light.DATA_LIGHTGROUPS])

    def test_process_groups_no_state(self):
        """Test the process_groups function when bridge returns no status."""
        self.setup_mocks_for_process_groups()
        self.mock_bridge.get_group.return_value = {'name': 'Group 0'}

        ret = hue_light.process_groups(
            self.hass, self.mock_api, self.mock_bridge, self.mock_bridge_type,
            None)

        self.assertEquals([], ret)
        self.assertEquals(
            {},
            self.hass.data[hue_light.DATA_KEY][hue_light.DATA_LIGHTGROUPS])

    @patch('homeassistant.components.light.hue.HueLight')
    def test_process_groups_some_groups(self, mock_hue_light):
        """Test the process_groups function with multiple groups."""
        self.setup_mocks_for_process_groups()
        self.mock_api.get.return_value = {
            1: {'state': 'on'}, 2: {'state': 'off'}}

        ret = hue_light.process_groups(
            self.hass, self.mock_api, self.mock_bridge, self.mock_bridge_type,
            None)

        self.assertEquals(len(ret), 2)
        mock_hue_light.assert_has_calls([
            call(
                1, {'state': 'on'}, self.mock_bridge, mock.ANY,
                self.mock_bridge_type, self.mock_bridge.allow_unreachable,
                self.mock_bridge.allow_in_emulated_hue, True),
            call(
                2, {'state': 'off'}, self.mock_bridge, mock.ANY,
                self.mock_bridge_type, self.mock_bridge.allow_unreachable,
                self.mock_bridge.allow_in_emulated_hue, True),
        ])
        self.assertEquals(
            len(self.hass.data[
                hue_light.DATA_KEY][hue_light.DATA_LIGHTGROUPS]),
            2)

    @patch('homeassistant.components.light.hue.HueLight')
    def test_process_groups_new_group(self, mock_hue_light):
        """
        Test the process_groups function with new groups.

        Test what happens when we already have a light and a new one shows up.
        """
        self.setup_mocks_for_process_groups()
        self.mock_api.get.return_value = {
            1: {'state': 'on'}, 2: {'state': 'off'}}
        self.hass.data[
            hue_light.DATA_KEY][hue_light.DATA_LIGHTGROUPS][1] = MagicMock()

        ret = hue_light.process_groups(
            self.hass, self.mock_api, self.mock_bridge, self.mock_bridge_type,
            None)

        self.assertEquals(len(ret), 1)
        mock_hue_light.assert_has_calls([
            call(
                2, {'state': 'off'}, self.mock_bridge, mock.ANY,
                self.mock_bridge_type, self.mock_bridge.allow_unreachable,
                self.mock_bridge.allow_in_emulated_hue, True),
        ])
        self.hass.data[hue_light.DATA_KEY][hue_light.DATA_LIGHTGROUPS][
            1].schedule_update_ha_state.assert_called_once_with()
        self.assertEquals(
            len(self.hass.data[
                hue_light.DATA_KEY][hue_light.DATA_LIGHTGROUPS]),
            2)


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
        self.mock_bridge_type = MagicMock()
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
        return hue_light.HueLight(
            light_id if light_id is not None else self.light_id,
            info if info is not None else self.mock_info,
            self.mock_bridge,
            (update_lights
             if update_lights is not None
             else self.mock_update_lights),
            self.mock_bridge_type,
            self.mock_allow_unreachable, self.mock_allow_in_emulated_hue,
            is_group if is_group is not None else self.mock_is_group)

    def test_unique_id_for_light(self):
        """Test the unique_id method with lights."""
        class_name = "<class 'homeassistant.components.light.hue.HueLight'>"

        light = self.buildLight(info={'uniqueid': 'foobar'})
        self.assertEquals(
            class_name+'.foobar',
            light.unique_id)

        light = self.buildLight(info={})
        self.assertEquals(
            class_name+'.Unnamed Device.Light.42',
            light.unique_id)

        light = self.buildLight(info={'name': 'my-name'})
        self.assertEquals(
            class_name+'.my-name.Light.42',
            light.unique_id)

        light = self.buildLight(info={'type': 'my-type'})
        self.assertEquals(
            class_name+'.Unnamed Device.my-type.42',
            light.unique_id)

        light = self.buildLight(info={'name': 'a name', 'type': 'my-type'})
        self.assertEquals(
            class_name+'.a name.my-type.42',
            light.unique_id)

    def test_unique_id_for_group(self):
        """Test the unique_id method with groups."""
        class_name = "<class 'homeassistant.components.light.hue.HueLight'>"

        light = self.buildLight(info={'uniqueid': 'foobar'}, is_group=True)
        self.assertEquals(
            class_name+'.foobar',
            light.unique_id)

        light = self.buildLight(info={}, is_group=True)
        self.assertEquals(
            class_name+'.Unnamed Device.Group.42',
            light.unique_id)

        light = self.buildLight(info={'name': 'my-name'}, is_group=True)
        self.assertEquals(
            class_name+'.my-name.Group.42',
            light.unique_id)

        light = self.buildLight(info={'type': 'my-type'}, is_group=True)
        self.assertEquals(
            class_name+'.Unnamed Device.my-type.42',
            light.unique_id)

        light = self.buildLight(
            info={'name': 'a name', 'type': 'my-type'},
            is_group=True)
        self.assertEquals(
            class_name+'.a name.my-type.42',
            light.unique_id)
