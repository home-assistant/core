"""Test config init."""

from homeassistant.components import config
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.setup import ATTR_COMPONENT, async_setup_component

from tests.async_mock import patch
from tests.common import mock_component


async def test_config_setup(hass, loop):
    """Test it sets up hassbian."""
    await async_setup_component(hass, "config", {})
    assert "config" in hass.config.components


async def test_load_on_demand_already_loaded(hass, aiohttp_client):
    """Test getting suites."""
    mock_component(hass, "zwave")

    with patch.object(config, "SECTIONS", []), patch.object(
        config, "ON_DEMAND", ["zwave"]
    ), patch(
        "homeassistant.components.config.zwave.async_setup", return_value=True
    ) as stp:

        await async_setup_component(hass, "config", {})

    await hass.async_block_till_done()
    assert stp.called


async def test_load_on_demand_on_load(hass, aiohttp_client):
    """Test getting suites."""
    with patch.object(config, "SECTIONS", []), patch.object(
        config, "ON_DEMAND", ["zwave"]
    ):
        await async_setup_component(hass, "config", {})

    assert "config.zwave" not in hass.config.components

    with patch(
        "homeassistant.components.config.zwave.async_setup", return_value=True
    ) as stp:
        hass.bus.async_fire(EVENT_COMPONENT_LOADED, {ATTR_COMPONENT: "zwave"})
        await hass.async_block_till_done()

    assert stp.called
