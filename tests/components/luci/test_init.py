"""Tests for the luci integration."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.luci.config_flow import InvalidAuth
from homeassistant.components.luci.const import DOMAIN
from homeassistant.components.luci.device_tracker import async_setup_scanner
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry

SCANNER_CONFIG = {
    CONF_HOST: "192.168.1.1",
    CONF_USERNAME: "root",
    CONF_PASSWORD: "password",
}


@pytest.mark.usefixtures("mock_luci_client")
async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_async_setup_scanner_invalid_auth(hass: HomeAssistant) -> None:
    """Test async_setup_scanner creates an issue on invalid auth."""
    with patch(
        "homeassistant.components.luci.config_flow._try_connect",
        side_effect=InvalidAuth,
    ):
        result = await async_setup_scanner(hass, SCANNER_CONFIG, AsyncMock())

    assert result is True
    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(DOMAIN, "yaml_import_invalid_auth")
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.ERROR
    assert issue.translation_placeholders == {"host": "192.168.1.1"}


async def test_async_setup_scanner_cannot_connect(hass: HomeAssistant) -> None:
    """Test async_setup_scanner creates an issue on connection failure."""
    with patch(
        "homeassistant.components.luci.config_flow._try_connect",
        side_effect=ConnectionError,
    ):
        result = await async_setup_scanner(hass, SCANNER_CONFIG, AsyncMock())

    assert result is True
    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(DOMAIN, "yaml_import_cannot_connect")
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.ERROR
    assert issue.translation_placeholders == {"host": "192.168.1.1"}
