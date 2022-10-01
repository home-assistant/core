"""Tests for the LaMetric integration."""
from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock

from aiohttp import ClientWebSocketResponse
from demetriek import LaMetricConnectionError, LaMetricConnectionTimeoutError
import pytest

from homeassistant.components.lametric.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.repairs import get_repairs


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lametric: MagicMock,
) -> None:
    """Test the LaMetric configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(mock_lametric.device.mock_calls) == 1

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "side_effect", [LaMetricConnectionTimeoutError, LaMetricConnectionError]
)
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lametric: MagicMock,
    side_effect: Exception,
) -> None:
    """Test the LaMetric configuration entry not ready."""
    mock_lametric.device.side_effect = side_effect

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(mock_lametric.device.mock_calls) == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_yaml_config_raises_repairs(
    hass: HomeAssistant,
    hass_ws_client: Callable[[HomeAssistant], Awaitable[ClientWebSocketResponse]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that YAML configuration raises an repairs issue."""
    await async_setup_component(
        hass, DOMAIN, {DOMAIN: {CONF_CLIENT_ID: "foo", CONF_CLIENT_SECRET: "bar"}}
    )

    assert "The 'lametric' option is deprecated" in caplog.text

    issues = await get_repairs(hass, hass_ws_client)
    assert len(issues) == 1
    assert issues[0]["issue_id"] == "manual_migration"
