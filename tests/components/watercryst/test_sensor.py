"""Tests for WATERCryst BIOCAT sensors."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pyocat.models import ModeId
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    patch,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.watercryst.coordinator import (
    MEASUREMENTS_POLLING_INTERVAL,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from .conftest import (
    basic_info_response,
    default_measurement_response,
    default_state_response,
)


@pytest.mark.usefixtures("mock_api_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all sensor entities."""

    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.watercryst._PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_available_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Test available sensor entities."""

    mock_api_client.get_device_info = AsyncMock(return_value=basic_info_response())

    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.watercryst._PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_availability(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test all sensor entities."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.watercryst._PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_device_pressure")

    assert state is not None
    assert state.state == "3.68"

    mock_api_client.get_measurements.side_effect = Exception()

    freezer.tick(MEASUREMENTS_POLLING_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_device_pressure")

    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    mock_api_client.get_measurements.side_effect = None

    freezer.tick(MEASUREMENTS_POLLING_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_device_pressure")

    assert state is not None
    assert state.state == "3.68"


async def test_missing_measurement_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test missing sensor values."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.watercryst._PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_device_pressure")

    assert state is not None
    assert state.state == "3.68"

    mock_api_client.get_measurements.return_value = None

    freezer.tick(MEASUREMENTS_POLLING_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_device_pressure")

    assert state is not None
    assert state.state == STATE_UNKNOWN

    mock_api_client.get_measurements.return_value = default_measurement_response()

    freezer.tick(MEASUREMENTS_POLLING_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_device_pressure")

    assert state is not None
    assert state.state == "3.68"


async def test_missing_state_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test missing sensor values."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.watercryst._PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_device_device_mode")

    assert state is not None
    assert state.state == ModeId.WATER_TREATMENT

    mock_api_client.get_state.return_value = None

    freezer.tick(MEASUREMENTS_POLLING_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_device_device_mode")

    assert state is not None
    assert state.state == STATE_UNKNOWN

    mock_api_client.get_state.return_value = default_state_response()

    freezer.tick(MEASUREMENTS_POLLING_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_device_device_mode")

    assert state is not None
    assert state.state == ModeId.WATER_TREATMENT
