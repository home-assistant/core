"""Test requirements module."""
import os
from unittest import mock

from homeassistant import loader, setup
from homeassistant.requirements import CONSTRAINT_FILE

from tests.common import get_test_home_assistant, MockModule


class TestRequirements:
    """Test the requirements module."""

    hass = None
    backup_cache = None

    # pylint: disable=invalid-name, no-self-use
    def setup_method(self, method):
        """Setup the test."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Clean up."""
        self.hass.stop()

    @mock.patch('os.path.dirname')
    @mock.patch('homeassistant.util.package.is_virtual_env',
                return_value=True)
    @mock.patch('homeassistant.util.package.install_package',
                return_value=True)
    def test_requirement_installed_in_venv(
            self, mock_install, mock_venv, mock_dirname):
        """Test requirement installed in virtual environment."""
        mock_venv.return_value = True
        mock_dirname.return_value = 'ha_package_path'
        self.hass.config.skip_pip = False
        loader.set_component(
            'comp', MockModule('comp', requirements=['package==0.0.1']))
        assert setup.setup_component(self.hass, 'comp')
        assert 'comp' in self.hass.config.components
        assert mock_install.call_args == mock.call(
            'package==0.0.1',
            constraints=os.path.join('ha_package_path', CONSTRAINT_FILE))

    @mock.patch('os.path.dirname')
    @mock.patch('homeassistant.util.package.is_virtual_env',
                return_value=False)
    @mock.patch('homeassistant.util.package.install_package',
                return_value=True)
    def test_requirement_installed_in_deps(
            self, mock_install, mock_venv, mock_dirname):
        """Test requirement installed in deps directory."""
        mock_dirname.return_value = 'ha_package_path'
        self.hass.config.skip_pip = False
        loader.set_component(
            'comp', MockModule('comp', requirements=['package==0.0.1']))
        assert setup.setup_component(self.hass, 'comp')
        assert 'comp' in self.hass.config.components
        assert mock_install.call_args == mock.call(
            'package==0.0.1', target=self.hass.config.path('deps'),
            constraints=os.path.join('ha_package_path', CONSTRAINT_FILE))
