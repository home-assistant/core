"""Test the ZhongHong setup and YAML import."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.zhong_hong.const import (
    CONF_GATEWAY_ADDRESS,
    DEFAULT_GATEWAY_ADDRESS,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import setup_integration
from .conftest import ENTITY_ID, HOST, FakeGateway

from tests.common import MockConfigEntry

YAML_CONFIG = {CLIMATE_DOMAIN: {"platform": DOMAIN, CONF_HOST: HOST}}


async def test_setup_and_unload(
    hass: HomeAssistant, mock_gateway: FakeGateway, mock_config_entry: MockConfigEntry
) -> None:
    """Test the gateway is listening while the entry is loaded."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_gateway.start_listen_calls == 1
    assert hass.states.get(ENTITY_ID) is not None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert mock_gateway.stop_listen_calls == 1


@pytest.mark.parametrize(
    ("attribute", "value"),
    [("discovery_error", OSError), ("discovery_result", [])],
    ids=["discovery_fails", "no_devices_found"],
)
async def test_setup_retries_without_devices(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
    mock_config_entry: MockConfigEntry,
    attribute: str,
    value: Any,
) -> None:
    """Test setup is retried when discovery does not yield devices."""
    setattr(mock_gateway, attribute, value)

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_gateway.start_listen_calls == 0


async def test_setup_stops_listener_when_first_refresh_fails(
    hass: HomeAssistant, mock_gateway: FakeGateway, mock_config_entry: MockConfigEntry
) -> None:
    """Test the listener is stopped when the entry fails after it was started."""
    mock_gateway.query_all_status_result = False

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_gateway.start_listen_calls == 1
    assert mock_gateway.stop_listen_calls == 1


async def test_yaml_import(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
    mock_socket_probe: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a YAML configuration is imported into a config entry."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data == {
        CONF_HOST: HOST,
        CONF_PORT: DEFAULT_PORT,
        CONF_GATEWAY_ADDRESS: DEFAULT_GATEWAY_ADDRESS,
    }
    assert hass.states.get(ENTITY_ID) is not None

    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


async def test_yaml_import_already_configured(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
    mock_socket_probe: AsyncMock,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an already imported YAML configuration still asks to be removed."""
    mock_config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, CLIMATE_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


async def test_yaml_import_with_an_unreachable_gateway(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an unreachable gateway is imported anyway and retried.

    The gateway takes a single connection at a time and can still be holding
    the one from the previous run, so a restart is exactly when the import is
    most likely to find it unreachable. The YAML platform is only set up once
    per start, so refusing to import here would strand the user on YAML.
    """
    mock_gateway.discovery_error = OSError

    assert await async_setup_component(hass, CLIMATE_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_RETRY

    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
