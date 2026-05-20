"""Tests for the Sense coordinators."""

from datetime import timedelta
import socket
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from sense_energy import (
    SenseAPIException,
    SenseAPITimeoutException,
    SenseAuthenticationException,
    SenseMFARequiredException,
    SenseWebsocketException,
)

from homeassistant.components.sense.const import (
    ACTIVE_UPDATE_RATE,
    DOMAIN,
    TREND_UPDATE_RATE,
)
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant

from . import setup_platform
from .const import DEVICE_1_NAME, MONITOR_ID

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize(
    "exception",
    [
        SenseAuthenticationException("auth expired"),
        SenseMFARequiredException("auth expired"),
    ],
)
async def test_trend_coordinator_auth_failure(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test that auth errors from the trend coordinator start a reauth flow."""
    await setup_platform(hass, config_entry, Platform.SENSOR)

    mock_sense.update_trend_data.side_effect = exception

    freezer.tick(timedelta(seconds=TREND_UPDATE_RATE))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_daily_energy")
    assert state.state == STATE_UNAVAILABLE

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    flow = flows[0]
    assert flow.get("step_id") == "reauth_validate"
    assert flow.get("handler") == DOMAIN
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == config_entry.entry_id


@pytest.mark.parametrize(
    "exception",
    [
        SenseAPIException("api error"),
        SenseAPITimeoutException("timeout"),
        TimeoutError("timeout"),
    ],
)
async def test_trend_coordinator_update_failure(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test that connection errors from the trend coordinator mark entities unavailable."""
    await setup_platform(hass, config_entry, Platform.SENSOR)

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_daily_energy")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    mock_sense.update_trend_data.side_effect = exception

    freezer.tick(timedelta(seconds=TREND_UPDATE_RATE))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_daily_energy")
    assert state.state == STATE_UNAVAILABLE


async def test_trend_coordinator_recovery(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that trend coordinator recovers after a transient failure."""
    await setup_platform(hass, config_entry, Platform.SENSOR)

    mock_sense.update_trend_data.side_effect = SenseAPIException("api error")

    freezer.tick(timedelta(seconds=TREND_UPDATE_RATE))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_daily_energy")
    assert state.state == STATE_UNAVAILABLE

    mock_sense.update_trend_data.side_effect = None

    freezer.tick(timedelta(seconds=TREND_UPDATE_RATE))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_daily_energy")
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "exception",
    [
        SenseAPITimeoutException("timeout"),
        TimeoutError("timeout"),
    ],
)
async def test_realtime_coordinator_timeout_failure(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test that timeout errors from the realtime coordinator mark entities unavailable."""
    await setup_platform(hass, config_entry, Platform.SENSOR)

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_energy")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    mock_sense.update_realtime.side_effect = exception

    freezer.tick(timedelta(seconds=ACTIVE_UPDATE_RATE))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_energy")
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "exception",
    [
        SenseWebsocketException("ws error"),
        socket.gaierror("addr info error"),
    ],
)
async def test_realtime_coordinator_websocket_failure(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test that websocket errors from the realtime coordinator mark entities unavailable."""
    await setup_platform(hass, config_entry, Platform.SENSOR)

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_energy")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    mock_sense.update_realtime.side_effect = exception

    freezer.tick(timedelta(seconds=ACTIVE_UPDATE_RATE))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_energy")
    assert state.state == STATE_UNAVAILABLE


async def test_realtime_coordinator_api_failure(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that API errors from the realtime coordinator mark entities unavailable."""
    await setup_platform(hass, config_entry, Platform.SENSOR)

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_energy")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    mock_sense.update_realtime.side_effect = SenseAPIException("api error")

    freezer.tick(timedelta(seconds=ACTIVE_UPDATE_RATE))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_energy")
    assert state.state == STATE_UNAVAILABLE


async def test_realtime_coordinator_recovery(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that realtime coordinator recovers after a transient failure."""
    await setup_platform(hass, config_entry, Platform.SENSOR)

    mock_sense.update_realtime.side_effect = SenseAPIException("api error")

    freezer.tick(timedelta(seconds=ACTIVE_UPDATE_RATE))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_energy")
    assert state.state == STATE_UNAVAILABLE

    mock_sense.update_realtime.side_effect = None

    freezer.tick(timedelta(seconds=ACTIVE_UPDATE_RATE))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_energy")
    assert state.state != STATE_UNAVAILABLE


async def test_trend_coordinator_name(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test that the trend coordinator is named correctly."""
    await setup_platform(hass, config_entry, Platform.SENSOR)

    assert config_entry.runtime_data.trends.name == f"Sense Trends {MONITOR_ID}"


async def test_realtime_coordinator_name(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test that the realtime coordinator is named correctly."""
    await setup_platform(hass, config_entry, Platform.SENSOR)

    assert config_entry.runtime_data.rt.name == f"Sense Realtime {MONITOR_ID}"


async def test_realtime_coordinator_binary_sensor_unavailable(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that binary sensor entities become unavailable on realtime coordinator failure."""
    await setup_platform(hass, config_entry, Platform.BINARY_SENSOR)

    state = hass.states.get(f"binary_sensor.{DEVICE_1_NAME.lower()}_power")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    mock_sense.update_realtime.side_effect = SenseAPIException("api error")

    freezer.tick(timedelta(seconds=ACTIVE_UPDATE_RATE))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(f"binary_sensor.{DEVICE_1_NAME.lower()}_power")
    assert state.state == STATE_UNAVAILABLE
