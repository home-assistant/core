"""Tests for the Rainforest RAVEn sensors."""

import asyncio
from datetime import timedelta
import functools
from unittest.mock import AsyncMock, patch

from aioraven.device import RAVEnConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import NETWORK_INFO

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("mock_entry")
async def test_sensors(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensors."""
    assert len(hass.states.async_all()) == 5

    await snapshot_platform(hass, entity_registry, snapshot, mock_entry.entry_id)


@pytest.mark.usefixtures("mock_entry")
async def test_device_update_error(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test handling of a device error during an update."""
    mock_device.get_network_info.side_effect = (RAVEnConnectionError, NETWORK_INFO)

    states = hass.states.async_all()
    assert len(states) == 5
    assert all(state.state != STATE_UNAVAILABLE for state in states)

    freezer.tick(timedelta(seconds=60))
    await hass.async_block_till_done()
    assert "Error fetching rainforest_raven data: RAVEnConnectionError" in caplog.text

    states = hass.states.async_all()
    assert len(states) == 5
    assert all(state.state == STATE_UNAVAILABLE for state in states)

    freezer.tick(timedelta(seconds=60))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    states = hass.states.async_all()
    assert len(states) == 5
    assert all(state.state != STATE_UNAVAILABLE for state in states)


@pytest.mark.usefixtures("mock_entry")
@patch("homeassistant.components.rainforest_raven.coordinator._DEVICE_TIMEOUT", 0.1)
async def test_device_update_timeout(
    hass: HomeAssistant, mock_device: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test handling of a device timeout during an update."""
    mock_device.get_network_info.side_effect = (
        functools.partial(asyncio.sleep, 10),
        NETWORK_INFO,
    )

    states = hass.states.async_all()
    assert len(states) == 5
    assert all(state.state != STATE_UNAVAILABLE for state in states)

    freezer.tick(timedelta(seconds=60))
    await hass.async_block_till_done()

    states = hass.states.async_all()
    assert len(states) == 5
    assert all(state.state == STATE_UNAVAILABLE for state in states)

    freezer.tick(timedelta(seconds=60))
    await hass.async_block_till_done()

    states = hass.states.async_all()
    assert len(states) == 5
    assert all(state.state == STATE_UNAVAILABLE for state in states)


@pytest.mark.usefixtures("mock_entry")
async def test_device_cache(
    hass: HomeAssistant, mock_device: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test that the device isn't re-opened for subsequent refreshes."""
    assert mock_device.get_network_info.call_count == 1
    assert mock_device.open.call_count == 1

    freezer.tick(timedelta(seconds=60))
    await hass.async_block_till_done()

    assert mock_device.get_network_info.call_count == 2
    assert mock_device.open.call_count == 1
