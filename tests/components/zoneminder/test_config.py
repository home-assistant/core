"""Tests for ZoneMinder YAML configuration validation."""

from __future__ import annotations

from homeassistant.components.zoneminder.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_SSL
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import MOCK_HOST


async def test_invalid_config_missing_host(hass: HomeAssistant) -> None:
    """Test that config without host is rejected."""
    config: dict = {DOMAIN: [{}]}

    result = await async_setup_component(hass, DOMAIN, config)
    assert not result


async def test_invalid_config_bad_ssl_type(hass: HomeAssistant) -> None:
    """Test that non-boolean ssl value is rejected."""
    config = {DOMAIN: [{CONF_HOST: MOCK_HOST, CONF_SSL: "not_bool"}]}

    result = await async_setup_component(hass, DOMAIN, config)
    assert not result
