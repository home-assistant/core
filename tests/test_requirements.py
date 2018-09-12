"""Test requirements module."""
import os
from unittest.mock import patch, call

from homeassistant import loader, setup
from homeassistant.requirements import (
    CONSTRAINT_FILE, PackageLoadable, async_process_requirements)

import pkg_resources

from tests.common import get_test_home_assistant, MockModule, mock_coro

RESOURCE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'resources'))

TEST_NEW_REQ = 'pyhelloworld3==1.0.0'

TEST_ZIP_REQ = 'file://{}#{}' \
    .format(os.path.join(RESOURCE_DIR, 'pyhelloworld3.zip'), TEST_NEW_REQ)


class TestRequirements:
    """Test the requirements module."""

    hass = None
    backup_cache = None

    # pylint: disable=invalid-name, no-self-use
    def setup_method(self, method):
        """Set up the test."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Clean up."""
        self.hass.stop()

    @patch('os.path.dirname')
    @patch('homeassistant.util.package.is_virtual_env', return_value=True)
    @patch('homeassistant.util.package.install_package', return_value=True)
    def test_requirement_installed_in_venv(
            self, mock_install, mock_venv, mock_dirname):
        """Test requirement installed in virtual environment."""
        mock_venv.return_value = True
        mock_dirname.return_value = 'ha_package_path'
        self.hass.config.skip_pip = False
        loader.set_component(
            self.hass, 'comp',
            MockModule('comp', requirements=['package==0.0.1']))
        assert setup.setup_component(self.hass, 'comp')
        assert 'comp' in self.hass.config.components
        assert mock_install.call_args == call(
            'package==0.0.1',
            constraints=os.path.join('ha_package_path', CONSTRAINT_FILE))

    @patch('os.path.dirname')
    @patch('homeassistant.util.package.is_virtual_env', return_value=False)
    @patch('homeassistant.util.package.install_package', return_value=True)
    def test_requirement_installed_in_deps(
            self, mock_install, mock_venv, mock_dirname):
        """Test requirement installed in deps directory."""
        mock_dirname.return_value = 'ha_package_path'
        self.hass.config.skip_pip = False
        loader.set_component(
            self.hass, 'comp',
            MockModule('comp', requirements=['package==0.0.1']))
        assert setup.setup_component(self.hass, 'comp')
        assert 'comp' in self.hass.config.components
        assert mock_install.call_args == call(
            'package==0.0.1', target=self.hass.config.path('deps'),
            constraints=os.path.join('ha_package_path', CONSTRAINT_FILE))


async def test_install_existing_package(hass):
    """Test an install attempt on an existing package."""
    with patch('homeassistant.util.package.install_package',
               return_value=mock_coro(True)) as mock_inst:
        assert await async_process_requirements(
            hass, 'test_component', ['hello==1.0.0'])

    assert len(mock_inst.mock_calls) == 1

    with patch('homeassistant.requirements.PackageLoadable.loadable',
               return_value=mock_coro(True)), \
            patch(
                'homeassistant.util.package.install_package') as mock_inst:
        assert await async_process_requirements(
            hass, 'test_component', ['hello==1.0.0'])

    assert len(mock_inst.mock_calls) == 0


async def test_check_package_global(hass):
    """Test for an installed package."""
    installed_package = list(pkg_resources.working_set)[0].project_name
    assert await PackageLoadable(hass).loadable(installed_package)


async def test_check_package_zip(hass):
    """Test for an installed zip package."""
    assert not await PackageLoadable(hass).loadable(TEST_ZIP_REQ)


async def test_package_loadable_installed_twice(hass):
    """Test that a package is loadable when installed twice.

    If a package is installed twice, only the first version will be imported.
    Test that package_loadable will only compare with the first package.
    """
    v1 = pkg_resources.Distribution(project_name='hello', version='1.0.0')
    v2 = pkg_resources.Distribution(project_name='hello', version='2.0.0')

    with patch('pkg_resources.find_distributions', side_effect=[[v1]]):
        assert not await PackageLoadable(hass).loadable('hello==2.0.0')

    with patch('pkg_resources.find_distributions', side_effect=[[v1], [v2]]):
        assert not await PackageLoadable(hass).loadable('hello==2.0.0')

    with patch('pkg_resources.find_distributions', side_effect=[[v2], [v1]]):
        assert await PackageLoadable(hass).loadable('hello==2.0.0')

    with patch('pkg_resources.find_distributions', side_effect=[[v2]]):
        assert await PackageLoadable(hass).loadable('hello==2.0.0')

    with patch('pkg_resources.find_distributions', side_effect=[[v2]]):
        assert await PackageLoadable(hass).loadable('Hello==2.0.0')
