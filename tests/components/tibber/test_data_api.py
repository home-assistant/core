"""Tests for the Tibber Data API coordinator and sensors."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
import tibber

from homeassistant.components.tibber import TibberRuntimeData
from homeassistant.components.tibber.const import DOMAIN
from homeassistant.components.tibber.coordinator import TibberDataAPICoordinator
from homeassistant.components.tibber.sensor import (
    TibberDataAPISensor,
    _async_setup_data_api_sensors,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed

from .conftest import create_tibber_device

from tests.common import MockConfigEntry


def _create_mock_runtime(async_get_client: AsyncMock) -> TibberRuntimeData:
    """Create a mock runtime data."""
    runtime = MagicMock(spec=TibberRuntimeData)
    runtime.async_get_client = async_get_client
    runtime.tibber_connection = MagicMock()
    runtime.session = MagicMock()
    runtime.data_api_coordinator = None
    return runtime


@pytest.fixture
def data_api_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a Data API Tibber config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ACCESS_TOKEN: "token"},
        unique_id="data-api",
    )
    entry.add_to_hass(hass)
    return entry


async def test_data_api_setup_adds_entities(
    hass: HomeAssistant,
    data_api_entry: MockConfigEntry,
) -> None:
    """Ensure Data API sensors are created and coordinator refreshes data."""
    client = MagicMock()
    client.get_all_devices = AsyncMock(
        return_value={"device-id": create_tibber_device(value=72.0)}
    )
    client.update_devices = AsyncMock(
        return_value={"device-id": create_tibber_device(value=83.0)}
    )
    async_get_client = AsyncMock(return_value=client)
    runtime = _create_mock_runtime(async_get_client)

    data_api_entry.runtime_data = runtime
    data_api_entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)

    coordinator = TibberDataAPICoordinator(hass, data_api_entry)
    await coordinator.async_config_entry_first_refresh()
    runtime.data_api_coordinator = coordinator

    added_entities: list[TibberDataAPISensor] = []

    def async_add_entities(entities: list[TibberDataAPISensor]) -> None:
        added_entities.extend(entities)

    await _async_setup_data_api_sensors(hass, data_api_entry, async_add_entities)

    assert async_get_client.await_count == 2
    client.get_all_devices.assert_awaited_once()
    client.update_devices.assert_awaited_once()

    assert len(added_entities) == 1
    sensor = added_entities[0]
    assert sensor.entity_description.key == "storage.stateOfCharge"
    assert sensor.native_value == 83.0
    assert sensor.available

    sensor.coordinator.data = {}
    sensor.coordinator.sensors_by_device = {}
    assert sensor.native_value is None
    assert not sensor.available


async def test_data_api_coordinator_first_refresh_failure(
    hass: HomeAssistant, data_api_entry: MockConfigEntry
) -> None:
    """Ensure network failures during setup raise ConfigEntryNotReady."""
    async_get_client = AsyncMock(side_effect=aiohttp.ClientError("boom"))
    runtime = _create_mock_runtime(async_get_client)
    data_api_entry.runtime_data = runtime

    coordinator = TibberDataAPICoordinator(hass, data_api_entry)
    data_api_entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)

    with pytest.raises(ConfigEntryNotReady):
        await coordinator.async_config_entry_first_refresh()
    assert isinstance(coordinator.last_exception, UpdateFailed)


async def test_data_api_coordinator_first_refresh_auth_failed(
    hass: HomeAssistant, data_api_entry: MockConfigEntry
) -> None:
    """Ensure auth failures during setup propagate."""
    async_get_client = AsyncMock(side_effect=ConfigEntryAuthFailed("invalid"))
    runtime = _create_mock_runtime(async_get_client)
    data_api_entry.runtime_data = runtime

    coordinator = TibberDataAPICoordinator(hass, data_api_entry)
    data_api_entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator.async_config_entry_first_refresh()


@pytest.mark.parametrize(
    "exception",
    [
        aiohttp.ClientError("err"),
        TimeoutError(),
        tibber.UserAgentMissingError("err"),
    ],
)
async def test_data_api_coordinator_update_failures(
    hass: HomeAssistant, data_api_entry: MockConfigEntry, exception: Exception
) -> None:
    """Ensure update failures are wrapped in UpdateFailed."""
    async_get_client = AsyncMock(side_effect=exception)
    runtime = _create_mock_runtime(async_get_client)
    data_api_entry.runtime_data = runtime

    coordinator = TibberDataAPICoordinator(hass, data_api_entry)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
