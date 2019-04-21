"""Test the bootstrapping."""
# pylint: disable=protected-access
import asyncio
import os
from unittest.mock import Mock, patch
import logging

import homeassistant.config as config_util
from homeassistant import bootstrap
import homeassistant.util.dt as dt_util

from tests.common import patch_yaml_files, get_test_config_dir, mock_coro

ORIG_TIMEZONE = dt_util.DEFAULT_TIME_ZONE
VERSION_PATH = os.path.join(get_test_config_dir(), config_util.VERSION_FILE)

_LOGGER = logging.getLogger(__name__)


# prevent .HA_VERSION file from being written
@patch(
    'homeassistant.bootstrap.conf_util.process_ha_config_upgrade', Mock())
@patch('homeassistant.util.location.detect_location_info',
       Mock(return_value=None))
@patch('os.path.isfile', Mock(return_value=True))
@patch('os.access', Mock(return_value=True))
@patch('homeassistant.bootstrap.async_enable_logging',
       Mock(return_value=True))
def test_from_config_file(hass):
    """Test with configuration file."""
    components = set(['browser', 'conversation', 'script'])
    files = {
        'config.yaml': ''.join('{}:\n'.format(comp) for comp in components)
    }

    with patch_yaml_files(files, True):
        yield from bootstrap.async_from_config_file('config.yaml', hass)

    assert components == hass.config.components


@patch('homeassistant.bootstrap.async_enable_logging', Mock())
@asyncio.coroutine
def test_home_assistant_core_config_validation(hass):
    """Test if we pass in wrong information for HA conf."""
    # Extensive HA conf validation testing is done
    result = yield from bootstrap.async_from_config_dict({
        'homeassistant': {
            'latitude': 'some string'
        }
    }, hass)
    assert result is None


def test_from_config_dict_not_mount_deps_folder(loop):
    """Test that we do not mount the deps folder inside from_config_dict."""
    with patch('homeassistant.bootstrap.is_virtual_env', return_value=False), \
        patch('homeassistant.core.HomeAssistant',
              return_value=Mock(loop=loop)), \
        patch('homeassistant.bootstrap.async_mount_local_lib_path',
              return_value=mock_coro()) as mock_mount, \
        patch('homeassistant.bootstrap.async_from_config_dict',
              return_value=mock_coro()):

        bootstrap.from_config_dict({}, config_dir='.')
        assert len(mock_mount.mock_calls) == 1

    with patch('homeassistant.bootstrap.is_virtual_env', return_value=True), \
        patch('homeassistant.core.HomeAssistant',
              return_value=Mock(loop=loop)), \
        patch('homeassistant.bootstrap.async_mount_local_lib_path',
              return_value=mock_coro()) as mock_mount, \
        patch('homeassistant.bootstrap.async_from_config_dict',
              return_value=mock_coro()):

        bootstrap.from_config_dict({}, config_dir='.')
        assert len(mock_mount.mock_calls) == 0


async def test_async_from_config_file_not_mount_deps_folder(loop):
    """Test that we not mount the deps folder inside async_from_config_file."""
    hass = Mock(
        async_add_executor_job=Mock(side_effect=lambda *args: mock_coro()))

    with patch('homeassistant.bootstrap.is_virtual_env', return_value=False), \
        patch('homeassistant.bootstrap.async_enable_logging',
              return_value=mock_coro()), \
        patch('homeassistant.bootstrap.async_mount_local_lib_path',
              return_value=mock_coro()) as mock_mount, \
        patch('homeassistant.bootstrap.async_from_config_dict',
              return_value=mock_coro()):

        await bootstrap.async_from_config_file('mock-path', hass)
        assert len(mock_mount.mock_calls) == 1

    with patch('homeassistant.bootstrap.is_virtual_env', return_value=True), \
        patch('homeassistant.bootstrap.async_enable_logging',
              return_value=mock_coro()), \
        patch('homeassistant.bootstrap.async_mount_local_lib_path',
              return_value=mock_coro()) as mock_mount, \
        patch('homeassistant.bootstrap.async_from_config_dict',
              return_value=mock_coro()):

        await bootstrap.async_from_config_file('mock-path', hass)
        assert len(mock_mount.mock_calls) == 0


async def test_load_hassio(hass):
    """Test that we load Hass.io component."""
    with patch.dict(os.environ, {}, clear=True):
        assert bootstrap._get_components(hass, {}) == set()

    with patch.dict(os.environ, {'HASSIO': '1'}):
        assert bootstrap._get_components(hass, {}) == {'hassio'}
