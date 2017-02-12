"""Test config init."""
import pytest

from homeassistant.bootstrap import async_setup_component

from tests.common import mock_http_component


@pytest.fixture(autouse=True)
def stub_http(hass):
    """Stub the HTTP component."""
    mock_http_component(hass)


def test_config_setup(hass, loop):
    """Test it sets up hassbian."""
    loop.run_until_complete(async_setup_component(hass, 'config', {}))
    assert 'config' in hass.config.components
