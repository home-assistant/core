"""Test the Laifen sensors."""

from dataclasses import replace
from unittest.mock import MagicMock

from laifen_ble import BrushingSession
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    mock_restore_cache_with_extra_data,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import SESSION, STATE

BATTERY_ENTITY_ID = "sensor.lftb01_p_1234_battery"
DURATION_ENTITY_ID = "sensor.lftb01_p_1234_last_brushing_duration"


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
