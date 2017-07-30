"""The tests for the panel_custom component."""
import os
import shutil
import unittest
from unittest.mock import Mock, patch

from homeassistant import setup
from homeassistant.components import panel_custom

from tests.common import get_test_home_assistant


@patch('homeassistant.components.frontend.setup',
       autospec=True, return_value=True)
class TestPanelCustom(unittest.TestCase):
    """Test the panel_custom component."""

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()
        shutil.rmtree(self.hass.config.path(panel_custom.PANEL_DIR),
                      ignore_errors=True)

    @patch('homeassistant.components.panel_custom.register_panel')
    def test_webcomponent_in_panels_dir(self, mock_register, _mock_setup):
        """Test if a web component is found in config panels dir."""
        config = {
            'panel_custom': {
                'name': 'todomvc',
            }
        }

        assert not setup.setup_component(self.hass, 'panel_custom', config)
        assert not mock_register.called

        path = self.hass.config.path(panel_custom.PANEL_DIR)
        os.mkdir(path)
        self.hass.data.pop(setup.DATA_SETUP)

        with open(os.path.join(path, 'todomvc.html'), 'a'):
            assert setup.setup_component(self.hass, 'panel_custom', config)
            assert mock_register.called

    @patch('homeassistant.components.panel_custom.register_panel')
    def test_webcomponent_custom_path(self, mock_register, _mock_setup):
        """Test if a web component is found in config panels dir."""
        filename = 'mock.file'

        config = {
            'panel_custom': {
                'name': 'todomvc',
                'webcomponent_path': filename,
                'sidebar_title': 'Sidebar Title',
                'sidebar_icon': 'mdi:iconicon',
                'url_path': 'nice_url',
                'config': 5,
            }
        }

        with patch('os.path.isfile', Mock(return_value=False)):
            assert not setup.setup_component(
                self.hass, 'panel_custom', config
            )
            assert not mock_register.called

        self.hass.data.pop(setup.DATA_SETUP)

        with patch('os.path.isfile', Mock(return_value=True)):
            with patch('os.access', Mock(return_value=True)):
                assert setup.setup_component(
                    self.hass, 'panel_custom', config
                )

                assert mock_register.called

                args = mock_register.mock_calls[0][1]
                assert args == (self.hass, 'todomvc', filename)

                kwargs = mock_register.mock_calls[0][2]
                assert kwargs == {
                    'config': 5,
                    'url_path': 'nice_url',
                    'sidebar_icon': 'mdi:iconicon',
                    'sidebar_title': 'Sidebar Title'
                }
