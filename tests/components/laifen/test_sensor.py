"""Test the Laifen sensors."""

from collections.abc import Awaitable, Callable
from dataclasses import replace
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from laifen_ble import BrushingSession
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.laifen.sensor import CURRENT_DURATION_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from . import (
    BATTERY_ENTITY_ID,
    CURRENT_DURATION_ENTITY_ID,
    DURATION_ENTITY_ID,
    setup_integration,
)
from .conftest import SESSION, STATE


@pytest.fixture
def platforms() -> list[Platform]:
    """Only set up the sensor platform."""
    return [Platform.SENSOR]


@pytest.fixture
def last_session() -> BrushingSession | None:
    """Return a toothbrush that already brushed."""
    return SESSION


@pytest.mark.usefixtures("init_integration")
async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensors of a connected toothbrush."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_pushed_state(hass: HomeAssistant, mock_toothbrush: MagicMock) -> None:
    """Test that pushed states and sessions update the sensors."""
    mock_toothbrush.state = replace(STATE, battery_level=91)
    mock_toothbrush.last_session = replace(SESSION, duration=118)
    mock_toothbrush.notify()
    await hass.async_block_till_done()

    assert hass.states.get(BATTERY_ENTITY_ID).state == "91"
    assert hass.states.get(DURATION_ENTITY_ID).state == "118"


@pytest.mark.usefixtures("init_integration")
async def test_unknown_battery_level(
    hass: HomeAssistant, mock_toothbrush: MagicMock
) -> None:
    """Test that an unknown battery level keeps the last one."""
    mock_toothbrush.state = replace(STATE, battery_level=None)
    mock_toothbrush.notify()
    await hass.async_block_till_done()

    assert hass.states.get(BATTERY_ENTITY_ID).state == "93"


@pytest.mark.usefixtures("init_integration")
async def test_sensors_while_asleep(
    hass: HomeAssistant, mock_toothbrush: MagicMock
) -> None:
    """Test that the last values are kept when the toothbrush falls asleep."""
    await mock_toothbrush.disconnect()
    await hass.async_block_till_done()

    assert hass.states.get(BATTERY_ENTITY_ID).state == "93"
    assert hass.states.get(DURATION_ENTITY_ID).state == "124"


@pytest.mark.parametrize("last_session", [None])
@pytest.mark.usefixtures("mock_toothbrush")
async def test_sensors_restored(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that the last values are restored while the toothbrush is asleep."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(BATTERY_ENTITY_ID, "88"),
                {"native_value": 88, "native_unit_of_measurement": "%"},
            ),
        ],
    )

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(BATTERY_ENTITY_ID).state == "88"
    assert hass.states.get(DURATION_ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.parametrize("last_session", [None])
@pytest.mark.usefixtures("mock_toothbrush")
async def test_sensors_unavailable_before_first_connection(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that sensors are unavailable before the first connection."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(BATTERY_ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get(DURATION_ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.parametrize("last_session", [None])
@pytest.mark.usefixtures("init_integration")
async def test_duration_unknown_while_connected(hass: HomeAssistant) -> None:
    """Test that the duration is unknown before the first brushing."""
    assert hass.states.get(DURATION_ENTITY_ID).state == STATE_UNKNOWN


async def _stop_motor(toothbrush: MagicMock) -> None:
    """Let the toothbrush report that the motor stopped."""
    toothbrush.state = STATE
    toothbrush.notify()


async def _fall_asleep(toothbrush: MagicMock) -> None:
    """Let the toothbrush disconnect while the motor runs."""
    await toothbrush.disconnect()


async def _tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Let one interval of the current brushing duration pass."""
    freezer.tick(CURRENT_DURATION_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.parametrize("end", [_stop_motor, _fall_asleep])
@pytest.mark.usefixtures("init_integration")
async def test_current_brushing_duration(
    hass: HomeAssistant,
    mock_toothbrush: MagicMock,
    freezer: FrozenDateTimeFactory,
    end: Callable[[MagicMock], Awaitable[None]],
) -> None:
    """Test that the current duration follows the session in progress."""
    assert hass.states.get(CURRENT_DURATION_ENTITY_ID).state == "0"

    mock_toothbrush.state = replace(STATE, running=True)
    mock_toothbrush.notify()
    await hass.async_block_till_done()

    assert hass.states.get(CURRENT_DURATION_ENTITY_ID).state == "0"

    mock_toothbrush.current_session = replace(SESSION, duration=5)
    await _tick(hass, freezer)

    assert hass.states.get(CURRENT_DURATION_ENTITY_ID).state == "5"

    mock_toothbrush.current_session = replace(SESSION, duration=6)
    await _tick(hass, freezer)

    assert hass.states.get(CURRENT_DURATION_ENTITY_ID).state == "6"

    mock_toothbrush.current_session = None
    await end(mock_toothbrush)
    await hass.async_block_till_done()

    assert hass.states.get(CURRENT_DURATION_ENTITY_ID).state == "0"

    mock_toothbrush.current_session = replace(SESSION, duration=7)
    await _tick(hass, freezer)

    assert hass.states.get(CURRENT_DURATION_ENTITY_ID).state == "0"


@pytest.mark.usefixtures("init_integration")
async def test_current_brushing_duration_after_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_toothbrush: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the current duration stops updating when the entry is unloaded."""
    mock_toothbrush.state = replace(STATE, running=True)
    mock_toothbrush.current_session = replace(SESSION, duration=5)
    mock_toothbrush.notify()
    await hass.async_block_till_done()

    assert hass.states.get(CURRENT_DURATION_ENTITY_ID).state == "5"

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    mock_toothbrush.current_session = replace(SESSION, duration=6)
    await _tick(hass, freezer)

    assert hass.states.get(CURRENT_DURATION_ENTITY_ID).state == STATE_UNAVAILABLE
