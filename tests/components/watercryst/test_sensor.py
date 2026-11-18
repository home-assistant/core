"""Tests for WATERCryst BIOCAT sensors."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pyocat import (
    WTCApiCancelledError,
    WTCApiDisabledError,
    WTCApiQuotaExceededError,
    WTCApiRequestError,
    WTCApiServerError,
    WTCApiTimeoutError,
    WTCApiUnauthorizedError,
    WTCApiValidationError,
)
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.watercryst.coordinator import (
    MEASUREMENTS_POLLING_INTERVAL,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from .conftest import basic_info_response


@pytest.mark.usefixtures("mock_api_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all sensor entities."""

    mock_config_entry.add_to_hass(hass)

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

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "exception",
    [
        WTCApiDisabledError(),
        WTCApiCancelledError(),
        WTCApiQuotaExceededError(),
        WTCApiRequestError(),
        WTCApiServerError(),
        WTCApiTimeoutError(),
        WTCApiValidationError(),
        WTCApiUnauthorizedError(),
    ],
)
async def test_availability(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test state sensor entities availability."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_device_pressure")

    assert state is not None
    assert state.state == "3.68"

    mock_api_client.get_measurements.side_effect = exception

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
