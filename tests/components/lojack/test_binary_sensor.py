"""Tests for the LoJack binary sensor platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from lojack_api import ApiError
from lojack_api.models import Location
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lojack.const import DOMAIN
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import TEST_LATITUDE, TEST_LONGITUDE, TEST_TIMESTAMP

from tests.common import MockConfigEntry, async_fire_time_changed

ENTITY_ID_BASE = "binary_sensor.2021_honda_accord"


@pytest.fixture(autouse=True)
def only_binary_sensor_platform():
    """Only set up the binary_sensor platform so snapshots cover one platform."""
    with patch(
        f"homeassistant.components.{DOMAIN}.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        yield


async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all binary sensor entities are created."""
    await setup_integration(hass, mock_config_entry)

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert entity_entries
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert (state := hass.states.get(entity_entry.entity_id))
        assert state == snapshot(name=f"{entity_entry.entity_id}-state")


async def test_connectivity_and_moving(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: MagicMock,
) -> None:
    """Test connected and moving binary sensors with telemetry present."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(f"{ENTITY_ID_BASE}_connectivity")
    assert state is not None
    assert state.state == STATE_ON

    state = hass.states.get(f"{ENTITY_ID_BASE}_moving")
    assert state is not None
    assert state.state == STATE_ON


async def test_moving_off_under_threshold(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: MagicMock,
    mock_device: MagicMock,
) -> None:
    """Test moving is off when speed is below the threshold."""
    mock_device.get_location = AsyncMock(
        return_value=Location(
            latitude=TEST_LATITUDE,
            longitude=TEST_LONGITUDE,
            timestamp=TEST_TIMESTAMP,
            speed=0.0,
        )
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(f"{ENTITY_ID_BASE}_moving")
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    ("speed", "expected_state"),
    [
        (None, STATE_UNKNOWN),
        (0.0, STATE_OFF),
        (0.5, STATE_OFF),
        (0.6, STATE_ON),
    ],
)
async def test_moving_threshold_boundaries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: MagicMock,
    mock_device: MagicMock,
    speed: float | None,
    expected_state: str,
) -> None:
    """Test moving around the movement threshold and with missing speed."""
    mock_device.get_location = AsyncMock(
        return_value=Location(
            latitude=TEST_LATITUDE,
            longitude=TEST_LONGITUDE,
            timestamp=TEST_TIMESTAMP,
            speed=speed,
        )
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(f"{ENTITY_ID_BASE}_moving")
    assert state is not None
    assert state.state == expected_state


async def test_connectivity_off_without_location_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: MagicMock,
    mock_device: MagicMock,
) -> None:
    """Test connected is off when no location data is available."""
    mock_device.get_location = AsyncMock(return_value=Location())
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(f"{ENTITY_ID_BASE}_connectivity")
    assert state is not None
    assert state.state == STATE_OFF


async def test_binary_sensors_become_unavailable_on_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: MagicMock,
    mock_device: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test binary sensors become unavailable when the coordinator update fails."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(f"{ENTITY_ID_BASE}_moving")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    mock_device.get_location = AsyncMock(side_effect=ApiError("API unavailable"))

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(f"{ENTITY_ID_BASE}_moving")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
