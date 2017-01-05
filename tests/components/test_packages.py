"""Test module for packages."""
from unittest.mock import patch
import pytest
from homeassistant.components import packages as pkg

import voluptuous as vol


# pylint: disable=redefined-outer-name
@pytest.fixture
def log_err():
    """Patch _log_error from packages."""
    with patch('homeassistant.components.packages._LOGGER.error') as logerr:
        yield logerr


def test_blocked_comps(log_err):
    """Test block config not allowed."""
    package_1 = {
        'homeassistant': {'name': 'Home'}
    }
    config = {
        'packages': {
            'bad_package': package_1
        }
    }
    pkg.merge_packages_config(config)

    assert log_err.call_count == 1
    assert config == {}
    assert 'not allowed' in log_err.call_args[0][0]


def test_merge_dict(log_err):
    """Test if we can merge dict based config - groups, input_*."""
    package_1 = {
        'input_boolean': {'ib1': None}
    }
    config = {
        'packages': {
            'bool_package': package_1
        },
        'input_boolean': {'ib2': None}
    }
    pkg.merge_packages_config(config)

    assert log_err.call_count == 0
    assert len(config) == 1
    assert len(config['input_boolean']) == 2


def test_merge_list(log_err):
    """Test if we can merge list based config - typically platforms."""
    package_1 = {
        'light': [{'platform': 'one'}]
    }
    config = {
        'packages': {
            'light_package': package_1
        },
        'light': [{'platform': 'two'}]
    }
    pkg.merge_packages_config(config)

    assert log_err.call_count == 0
    assert len(config) == 1
    assert len(config['light']) == 2


def test_new(log_err):
    """Test adding new config to outer scope."""
    package_1 = {
        'light': {'platform': 'one'}
    }
    config = {
        'packages': {
            'light_package': package_1
        }
    }
    pkg.merge_packages_config(config)

    assert log_err.call_count == 0
    assert len(config) == 1
    assert len(config['light']) == 1


def test_schema_err(log_err):
    """Test if we have a type mismatch for packages."""
    package_1 = {
        'input_boolean': None,
    }
    config = {
        'packages': {
            'bool_package': package_1
        }
    }
    with pytest.raises(vol.Invalid):
        pkg.merge_packages_config(config)


def test_type_mismatch(log_err):
    """Test if we have a type mismatch for packages."""
    package_1 = {
        'input_boolean': [{'ib1': None}],
        'light': {'platform': 'one'}
    }
    config = {
        'packages': {
            'bool_package': package_1
        },
        'input_boolean': {'ib2': None},
        'light': [{'platform': 'two'}]
    }
    pkg.merge_packages_config(config)

    assert log_err.call_count == 2
    assert len(config) == 2
    assert len(config['input_boolean']) == 1
    assert len(config['light']) == 1
