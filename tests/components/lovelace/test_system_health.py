"""Tests for Lovelace system health."""
from typing import Any
from unittest.mock import patch

from homeassistant.components.lovelace import dashboard
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import get_system_health_info


async def test_system_health_info_autogen(hass: HomeAssistant) -> None:
    """Test system health info endpoint."""
    assert await async_setup_component(hass, "lovelace", {})
    assert await async_setup_component(hass, "system_health", {})
    info = await get_system_health_info(hass, "lovelace")
    assert info == {"dashboards": 1, "mode": "auto-gen", "resources": 0}


async def test_system_health_info_storage(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test system health info endpoint."""
    assert await async_setup_component(hass, "system_health", {})
    hass_storage[dashboard.CONFIG_STORAGE_KEY_DEFAULT] = {
        "key": "lovelace",
        "version": 1,
        "data": {"config": {"resources": [], "views": []}},
    }
    assert await async_setup_component(hass, "lovelace", {})
    await hass.async_block_till_done()
    info = await get_system_health_info(hass, "lovelace")
    assert info == {"dashboards": 1, "mode": "storage", "resources": 0, "views": 0}


async def test_system_health_info_yaml(hass: HomeAssistant) -> None:
    """Test system health info endpoint."""
    assert await async_setup_component(hass, "system_health", {})
    assert await async_setup_component(hass, "lovelace", {"lovelace": {"mode": "YAML"}})
    await hass.async_block_till_done()
    with patch(
        "homeassistant.components.lovelace.dashboard.load_yaml",
        return_value={"views": [{"cards": []}]},
    ):
        info = await get_system_health_info(hass, "lovelace")
    assert info == {"dashboards": 1, "mode": "yaml", "resources": 0, "views": 1}


async def test_system_health_info_yaml_not_found(hass: HomeAssistant) -> None:
    """Test system health info endpoint."""
    assert await async_setup_component(hass, "system_health", {})
    assert await async_setup_component(hass, "lovelace", {"lovelace": {"mode": "YAML"}})
    await hass.async_block_till_done()
    info = await get_system_health_info(hass, "lovelace")
    assert info == {
        "dashboards": 1,
        "mode": "yaml",
        "error": "{} not found".format(hass.config.path("ui-lovelace.yaml")),
        "resources": 0,
    }
