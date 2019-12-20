"""Tests for the local_ip component."""
import pytest

from homeassistant.components.local_ip import DOMAIN
from homeassistant.setup import async_setup_component
from homeassistant.util import get_local_ip


@pytest.fixture(name="config")
def config_fixture():
    """Create hass config fixture."""
    return {DOMAIN: {"name": "test"}}


async def test_basic_setup(hass, config):
    """Test component setup creates entry from config."""
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    local_ip = get_local_ip()
    state = hass.states.get("sensor.test")
    assert state
    assert state.state == local_ip


async def test_config_flow(hass):
    """Test we can finish a config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "test"}
    )
    assert result["type"] == "create_entry"

    await hass.async_block_till_done()
    state = hass.states.get("sensor.test")
    assert state
