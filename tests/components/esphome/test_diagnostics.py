"""Tests for the diagnostics data provided by the ESPHome integration."""

from aiohttp import ClientSession

from homeassistant.components.esphome import CONF_NOISE_PSK
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_diagnostics(
    hass: HomeAssistant, hass_client: ClientSession, init_integration: MockConfigEntry
):
    """Test diagnostics for config entry."""
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert isinstance(result, dict)
    assert result["config"]["data"] == {
        CONF_HOST: "192.168.1.2",
        CONF_PORT: 6053,
        CONF_PASSWORD: "**REDACTED**",
        CONF_NOISE_PSK: "**REDACTED**",
    }
    assert result["config"]["unique_id"] == "esphome-device"
