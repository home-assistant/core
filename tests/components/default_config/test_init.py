"""Test the default_config init."""
from unittest.mock import patch

import pytest

from homeassistant.setup import async_setup_component

from tests.common import MockDependency, mock_coro


@pytest.fixture(autouse=True)
def zeroconf_mock():
    """Mock zeroconf."""
    with MockDependency("zeroconf") as mocked_zeroconf:
        mocked_zeroconf.Zeroconf.return_value.register_service.return_value = mock_coro(
            True
        )
        yield


@pytest.fixture(autouse=True)
def netdisco_mock():
    """Mock netdisco."""
    with MockDependency("netdisco", "discovery"):
        yield


@pytest.fixture(autouse=True)
def recorder_url_mock():
    """Mock recorder url."""
    with patch("homeassistant.components.recorder.DEFAULT_URL", "sqlite://"):
        yield


async def test_setup(hass):
    """Test setup."""
    assert await async_setup_component(hass, "default_config", {"foo": "bar"})
