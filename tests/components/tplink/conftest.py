"""tplink conftest."""

import pytest

from . import _patch_discovery

from tests.common import mock_device_registry, mock_registry


@pytest.fixture
def mock_discovery():
    """Mock python-kasa discovery."""
    with _patch_discovery() as mock_discover:
        mock_discover.return_value = {}
        yield mock_discover


@pytest.fixture(name="device_reg")
def device_reg_fixture(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture(name="entity_reg")
def entity_reg_fixture(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


@pytest.fixture(autouse=True)
def tplink_mock_get_source_ip(mock_get_source_ip):
    """Mock network util's async_get_source_ip."""
