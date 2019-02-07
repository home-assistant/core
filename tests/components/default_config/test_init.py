"""Test the default_config init."""
from homeassistant.setup import async_setup_component

import pytest

from tests.common import MockDependency


@pytest.fixture(autouse=True)
def netdisco_mock():
    """Mock netdisco."""
    with MockDependency('netdisco', 'discovery'):
        yield


async def test_setup(hass):
    """Test setup."""
    assert await async_setup_component(hass, 'default_config', {})
