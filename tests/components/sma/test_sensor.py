"""Test the SMA sensor platform."""

from collections.abc import Generator
import logging
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pysma import SmaAuthenticationException, SmaConnectionException, SmaReadException
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sma.const import DEFAULT_SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_sma_client: Generator,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.sma.PLATFORMS",
        [Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("exception"),
    [
        (SmaConnectionException),
        (SmaAuthenticationException),
        (SmaReadException),
        (Exception),
    ],
)
async def test_refresh_exceptions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sma_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test the coordinator refresh exceptions."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_sma_client.read.side_effect = exception

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()

    state = hass.states.get("sensor.sma_device_name_battery_capacity_a")
    assert state
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("exception", "level"),
    [
        pytest.param(SmaConnectionException, logging.INFO, id="unreachable"),
        pytest.param(SmaReadException, logging.ERROR, id="read_error"),
    ],
)
async def test_refresh_log_level(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sma_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    exception: type[Exception],
    level: int,
) -> None:
    """Test an unreachable device is logged at info level."""
    await setup_integration(hass, mock_config_entry)

    mock_sma_client.read.side_effect = exception

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()

    assert [
        record.levelno
        for record in caplog.records
        if record.name == "homeassistant.components.sma.coordinator"
        and record.levelno > logging.DEBUG
    ] == [level]
