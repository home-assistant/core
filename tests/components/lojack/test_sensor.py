"""Tests for the LoJack sensor platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from lojack_api import ApiError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lojack.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import TEST_BATTERY_VOLTAGE, TEST_ODOMETER, TEST_SPEED, TEST_TIMESTAMP

from tests.common import MockConfigEntry, async_fire_time_changed

ENTITY_ID_BASE = "sensor.2021_honda_accord"


@pytest.fixture(autouse=True)
def only_sensor_platform():
    """Only set up the sensor platform so snapshots cover one platform."""
    with patch(
        f"homeassistant.components.{DOMAIN}.PLATFORMS",
        [Platform.SENSOR],
    ):
        yield


async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all sensor entities are created."""
    await setup_integration(hass, mock_config_entry)

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert entity_entries
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert (state := hass.states.get(entity_entry.entity_id))
        assert state == snapshot(name=f"{entity_entry.entity_id}-state")


async def test_sensor_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: MagicMock,
) -> None:
    """Test sensor values from the coordinator data."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(f"{ENTITY_ID_BASE}_distance")
    assert state is not None
    # Native unit is miles; HA converts to the metric test unit system (km)
    assert float(state.state) == pytest.approx(TEST_ODOMETER * 1.609344)

    state = hass.states.get(f"{ENTITY_ID_BASE}_speed")
    assert state is not None
    # Native unit is mph; HA converts to the metric test unit system (km/h)
    assert float(state.state) == pytest.approx(TEST_SPEED * 1.609344)

    state = hass.states.get(f"{ENTITY_ID_BASE}_voltage")
    assert state is not None
    assert float(state.state) == pytest.approx(TEST_BATTERY_VOLTAGE)


async def test_last_reported_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: MagicMock,
) -> None:
    """Test the location timestamp sensor."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(f"{ENTITY_ID_BASE}_timestamp")
    assert state is not None
    assert state.state == TEST_TIMESTAMP.isoformat()


async def test_sensor_becomes_unavailable_on_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: MagicMock,
    mock_device: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors become unavailable when the coordinator update fails."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(f"{ENTITY_ID_BASE}_distance")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    mock_device.get_location = AsyncMock(side_effect=ApiError("API unavailable"))

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(f"{ENTITY_ID_BASE}_distance")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
