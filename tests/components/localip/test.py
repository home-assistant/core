"""Tests for the localip component."""
import pytest

from homeassistant.components.localip import DOMAIN
from homeassistant.setup import async_setup_component


@pytest.fixture(name="config")
def config_fixture():
    """Create hass config fixture."""
    return {DOMAIN: {}}


async def test_async_setup(hass, config):
    """Test component setup creates entry from config."""
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
