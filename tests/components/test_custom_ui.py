"""The tests for the custom_ui component."""
import os
import shutil
import unittest
from unittest.mock import Mock, patch

from homeassistant import bootstrap
from homeassistant.components import custom_ui

from tests.common import get_test_home_assistant


@patch('homeassistant.components.frontend.setup',
       autospec=True, return_value=True)
class TestCustomUi(unittest.TestCase):
    """Test the panel_custom component."""

    hass = None

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()
        shutil.rmtree(self.hass.config.path(custom_ui.CUSTOM_UI_DIR),
                      ignore_errors=True)

    @patch('homeassistant.components.custom_ui.register_custom_ui')
    def test_webcomponent_dir(self, mock_register, _mock_setup):
        """Test if a web component is found in config custom_ui dir."""
        config = {
            'custom_ui': {
                'name': 'custom_name',
            }
        }

        assert not bootstrap.setup_component(self.hass, 'custom_ui', config)
        assert not mock_register.called

        path = self.hass.config.path(custom_ui.CUSTOM_UI_DIR)
        os.mkdir(path)

        with open(os.path.join(path, 'custom_name.html'), 'a'):
            assert bootstrap.setup_component(self.hass, 'custom_ui', config)
            assert mock_register.called

    @patch('homeassistant.components.custom_ui.register_custom_ui')
    def test_webcomponent_custom_path(self, mock_register, _mock_setup):
        """Test if a web component is found in custom config dir."""
        filename = 'mock.file'

        config = {
            'custom_ui': {
                'name': 'custom_name',
                'webcomponent_path': filename,
                'url_path': 'nice_url',
                'config': 5,
            }
        }

        with patch('os.path.isfile', Mock(return_value=False)):
            assert not bootstrap.setup_component(
                self.hass, 'custom_ui', config
            )
            assert not mock_register.called

        with patch('os.path.isfile', Mock(return_value=True)):
            with patch('os.access', Mock(return_value=True)):
                assert bootstrap.setup_component(
                    self.hass, 'custom_ui', config
                )

                assert mock_register.called

                args = mock_register.mock_calls[0][1]
                assert args == (self.hass, 'custom_name', filename)

                kwargs = mock_register.mock_calls[0][2]
                assert kwargs == {
                    'config': 5,
                    'url_path': 'nice_url',
                }
