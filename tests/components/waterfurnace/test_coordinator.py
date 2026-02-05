"""Tests for WaterFurnace coordinator."""

from __future__ import annotations

import asyncio
from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
import pytest
from waterfurnace.waterfurnace import WFCredentialError, WFException

from homeassistant.components.waterfurnace.const import UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("init_integration")
async def test_coordinator_update_success(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test successful coordinator data update."""
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.wf_test_gwid_12345_totalunitpower")
    assert state
    assert state.state == "1500"


@pytest.mark.usefixtures("init_integration")
async def test_coordinator_update_failure(
    hass: HomeAssistant,
    mock_waterfurnace_client: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator handles update failure."""
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.wf_test_gwid_12345_totalunitpower")
    assert state
    assert state.state == "1500"

    mock_waterfurnace_client.read_with_retry.side_effect = WFException(
        "Connection failed"
    )
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.wf_test_gwid_12345_totalunitpower")
    assert state
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_coordinator_update_timeout(
    hass: HomeAssistant,
    mock_waterfurnace_client: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator handles timeout."""
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.wf_test_gwid_12345_totalunitpower")
    assert state
    assert state.state == "1500"

    mock_waterfurnace_client.read_with_retry.side_effect = asyncio.TimeoutError
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.wf_test_gwid_12345_totalunitpower")
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_coordinator_setup_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_waterfurnace_client: Mock,
) -> None:
    """Test config entry goes to SETUP_ERROR when credentials fail during setup."""
    mock_waterfurnace_client.login.side_effect = WFCredentialError(
        "Authentication failed"
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
