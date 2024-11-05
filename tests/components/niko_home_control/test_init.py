"""Tests for the niko_home_control component."""

from unittest.mock import AsyncMock

from homeassistant.components.niko_home_control.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_import_flow(
    hass: HomeAssistant,
    mock_nhc: AsyncMock,
    issue_registry: ir.IssueRegistry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test import flow."""
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {CONF_HOST: "0.0.0.0", CONF_NAME: "niko_home_control"}}
    )
    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert (
        HOMEASSISTANT_DOMAIN,
        "deprecated_yaml_niko_home_control",
    ) in issue_registry.issues


async def test_import_flow_already_exists(
    hass: HomeAssistant,
    mock_nhc: AsyncMock,
    issue_registry: ir.IssueRegistry,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test import flow when entry already exists."""
    mock_config_entry.add_to_hass(hass)
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {CONF_HOST: "0.0.0.0", CONF_NAME: "niko_home_control"}}
    )
    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert (
        HOMEASSISTANT_DOMAIN,
        "deprecated_yaml_niko_home_control",
    ) in issue_registry.issues


async def test_import_flow_error(
    hass: HomeAssistant,
    mock_nhc: AsyncMock,
    issue_registry: ir.IssueRegistry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test import flow when error occurs."""
    mock_nhc.return_value = False
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {CONF_HOST: "0.0.0.0", CONF_NAME: "niko_home_control"}}
    )
    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    assert (
        DOMAIN,
        "deprecated_yaml_import_issue_cannot_connect",
    ) in issue_registry.issues
