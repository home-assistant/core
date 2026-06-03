"""Tests for the Schluter DITRA-HEAT __init__."""

from unittest.mock import AsyncMock

from homeassistant.components.schluter.api import (
    CannotConnectError,
    InvalidCredentialsError,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import setup_integration
from .conftest import DOMAIN

from tests.common import MockConfigEntry


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_schluter_api: AsyncMock,
) -> None:
    """Test loading and unloading the config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_schluter_api: AsyncMock,
) -> None:
    """Test that a connection error on setup puts the entry in SETUP_RETRY."""
    mock_schluter_api.async_get_session.side_effect = CannotConnectError

    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_invalid_credentials(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_schluter_api: AsyncMock,
) -> None:
    """Test that invalid credentials on setup trigger a reauth flow."""
    mock_schluter_api.async_get_session.side_effect = InvalidCredentialsError

    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler("schluter")
    assert any(f["context"]["source"] == "reauth" for f in flows)


async def test_async_setup_no_yaml(hass: HomeAssistant) -> None:
    """Test that async_setup returns True when no YAML config is present."""
    result = await async_setup_component(hass, DOMAIN, {})
    assert result is True


async def test_async_setup_yaml_triggers_import(
    hass: HomeAssistant,
    mock_schluter_api: AsyncMock,
) -> None:
    """Test that YAML config triggers an import flow."""
    result = await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {CONF_USERNAME: "user@example.com", CONF_PASSWORD: "secret"}},
    )
    assert result is True
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(flows) == 0
    assert len(entries) == 1
    assert entries[0].data[CONF_USERNAME] == "user@example.com"
