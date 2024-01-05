"""Tests for the Velux component initialisation."""
from typing import cast
from unittest.mock import patch

from homeassistant.components.velux import DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import DATA_REGISTRY, IssueRegistry
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from .conftest import TestPyVLX


@patch("homeassistant.components.velux.PyVLX", new=TestPyVLX)
async def test_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Test loading and unloading setup entry."""
    assert not hass.data.get(DOMAIN)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state == ConfigEntryState.LOADED
    pyvlx: TestPyVLX = hass.data[DOMAIN][config_entry.entry_id]
    assert not pyvlx.reboot_initiated
    assert not pyvlx.disconnected
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert pyvlx.reboot_initiated
    assert pyvlx.disconnected
    assert config_entry.state == ConfigEntryState.NOT_LOADED


@patch("homeassistant.components.velux.PyVLX", new=TestPyVLX)
async def test_reboot_service(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Test reboot service."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    pyvlx: TestPyVLX = hass.data[DOMAIN][config_entry.entry_id]
    assert not pyvlx.reboot_initiated
    await hass.services.async_call(DOMAIN, "reboot_gateway")
    await hass.async_block_till_done()
    assert pyvlx.reboot_initiated


@patch("homeassistant.components.velux.PyVLX", new=TestPyVLX)
@patch("homeassistant.components.velux.config_flow.PyVLX", new=TestPyVLX)
async def test_async_setup(hass: HomeAssistant, config_type: ConfigType) -> None:
    """Test async_setup method."""
    with patch("homeassistant.components.velux.PyVLX", autospec=True) as pyvlx:
        assert not hass.data.get(DOMAIN)
        assert DOMAIN not in hass.config.components
        assert await async_setup_component(hass=hass, domain=DOMAIN, config=config_type)
        await hass.async_block_till_done()
        assert DOMAIN in hass.config.components
        await hass.async_block_till_done()
        pyvlx.assert_called_once_with(
            host=config_type[DOMAIN][CONF_HOST],
            password=config_type[DOMAIN][CONF_PASSWORD],
        )
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1
        issue_registry = cast(IssueRegistry, hass.data[DATA_REGISTRY])
        assert issue_registry.issues.get((DOMAIN, "deprecated_yaml"))
