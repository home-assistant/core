"""Test the bootstrapping."""
# pylint: disable=protected-access
import asyncio
import os
from unittest.mock import Mock, patch
import logging

import homeassistant.config as config_util
from homeassistant import bootstrap
import homeassistant.util.dt as dt_util

from tests.common import patch_yaml_files, get_test_config_dir

ORIG_TIMEZONE = dt_util.DEFAULT_TIME_ZONE
VERSION_PATH = os.path.join(get_test_config_dir(), config_util.VERSION_FILE)

_LOGGER = logging.getLogger(__name__)


# prevent .HA_VERSION file from being written
@patch(
    'homeassistant.bootstrap.conf_util.process_ha_config_upgrade', Mock())
@patch('homeassistant.util.location.detect_location_info',
       Mock(return_value=None))
@patch('homeassistant.bootstrap.async_register_signal_handling', Mock())
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
        yield from bootstrap.async_from_config_file('config.yaml')

    assert components == hass.config.components


@asyncio.coroutine
@patch('homeassistant.bootstrap.async_enable_logging', Mock())
@patch('homeassistant.bootstrap.async_register_signal_handling', Mock())
def test_home_assistant_core_config_validation(hass):
    """Test if we pass in wrong information for HA conf."""
    # Extensive HA conf validation testing is done
    result = yield from bootstrap.async_from_config_dict({
        'homeassistant': {
            'latitude': 'some string'
        }
    }, hass)
    assert result is None
