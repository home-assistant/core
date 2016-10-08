import unittest
import unittest.mock

from homeassistant.bootstrap import setup_component
from homeassistant.components.light import hue
from homeassistant.const import CONF_FILENAME, CONF_HOST, CONF_USERNAME

from tests.common import get_test_home_assistant


class TestHue(unittest.TestCase):
    def setUp(self):
        self.hass_mock = get_test_home_assistant()

        setup_component(self.hass_mock, 'light')

        self.config = {
            CONF_HOST: 'test',
            CONF_USERNAME: 'test',
            hue.CONF_ALLOW_UNREACHABLE: False,
            CONF_FILENAME: 'fake/path'
        }

        hue._CONFIGURING = {}
        hue._CONFIGURED_BRIDGES = {}

    def tearDown(self):
        self.hass_mock.stop()

    @unittest.mock.patch('homeassistant.components.light.hue.setup_bridge')
    @unittest.mock.patch('socket.gethostbyname')
    def test_setup_platform_uses_discovery_info(self,
                                                socket_mock,
                                                setup_bridge_mock):
        hue.setup_platform(
            self.hass_mock,
            self.config,
            None,
            [None, 'http://test:1234']
        )

        setup_bridge_mock.assert_called_once_with(
            'test',
            None,
            self.hass_mock,
            None,
            self.config[CONF_FILENAME],
            self.config[hue.CONF_ALLOW_UNREACHABLE],
        )

    @unittest.mock.patch(
        'homeassistant.components.light.hue._find_host_from_config')
    def test_setup_platform_fails(self, _find_host_from_config_mock):
        _find_host_from_config_mock.return_value = (None, None)
        del self.config[CONF_HOST]

        self.assertFalse(
            hue.setup_platform(
                self.hass_mock,
                self.config,
                None
            )
        )

    @unittest.mock.patch('homeassistant.components.light.hue.setup_bridge')
    @unittest.mock.patch('socket.gethostbyname')
    def test_setup_platform_being_configured(self,
                                             socket_mock,
                                             setup_bridge_mock):
        socket_mock.return_value = 'test'

        hue._CONFIGURED_BRIDGES['test'] = True

        hue.setup_platform(
            self.hass_mock,
            self.config,
            None
        )

        setup_bridge_mock.assert_not_called()

    @unittest.mock.patch('homeassistant.components.light.hue.setup_bridge')
    @unittest.mock.patch('socket.gethostbyname')
    def test_setup_platform_already_configured(self,
                                               socket_mock,
                                               setup_bridge_mock):
        socket_mock.return_value = 'test'

        hue._CONFIGURING['test'] = True

        hue.setup_platform(
            self.hass_mock,
            self.config,
            None
        )

        setup_bridge_mock.assert_not_called()

    @unittest.mock.patch('homeassistant.components.light.hue.setup_bridge')
    @unittest.mock.patch('socket.gethostbyname')
    def test_setup_platform(self, socket_mock, setup_bridge_mock):
        socket_mock.return_value = 'test'

        hue.setup_platform(
            self.hass_mock,
            self.config,
            None
        )

        setup_bridge_mock.assert_called_once_with(
            self.config[CONF_HOST],
            self.config[CONF_USERNAME],
            self.hass_mock,
            None,
            self.config[CONF_FILENAME],
            self.config[hue.CONF_ALLOW_UNREACHABLE],
        )
