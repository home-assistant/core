"""Tests for the Tibber Data API coordinator and sensors."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
import tibber

from homeassistant.components.tibber.const import (
    API_TYPE_DATA_API,
    CONF_API_TYPE,
    DOMAIN,
)
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


@pytest.fixture
def data_api_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a Data API Tibber config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ACCESS_TOKEN: "token", CONF_API_TYPE: API_TYPE_DATA_API},
        unique_id="data-api",
    )
    entry.add_to_hass(hass)
    return entry


async def test_data_api_setup_adds_entities(
    hass: HomeAssistant,
    data_api_entry: MockConfigEntry,
) -> None:
    """Ensure Data API sensors are created and coordinator refreshes data."""
    runtime = MagicMock()
    client = MagicMock()
    client.get_all_devices = AsyncMock(
        return_value={"device-id": create_tibber_device(value=72.0)}
    )
    client.update_devices = AsyncMock(
        return_value={"device-id": create_tibber_device(value=83.0)}
    )
    runtime.async_get_client = AsyncMock(return_value=client)

    hass.data.setdefault(DOMAIN, {})[API_TYPE_DATA_API] = runtime

    added_entities: list[TibberDataAPISensor] = []

    def async_add_entities(entities: list[TibberDataAPISensor]) -> None:
        added_entities.extend(entities)

    data_api_entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)

    await _async_setup_data_api_sensors(hass, data_api_entry, async_add_entities)

    assert runtime.async_get_client.await_count == 2
    client.get_all_devices.assert_awaited_once()
    client.update_devices.assert_awaited_once()

    assert len(added_entities) == 1
    sensor = added_entities[0]
    assert sensor.entity_description.key == "storage.stateOfCharge"
    assert sensor.native_value == 83.0
    assert sensor.available

    sensor.coordinator.data = {}
    assert sensor.native_value is None
    assert not sensor.available


async def test_data_api_coordinator_first_refresh_failure(
    hass: HomeAssistant, data_api_entry: MockConfigEntry
) -> None:
    """Ensure network failures during setup raise ConfigEntryNotReady."""
    runtime = MagicMock()
    runtime.async_get_client = AsyncMock(side_effect=aiohttp.ClientError("boom"))
    hass.data.setdefault(DOMAIN, {})[API_TYPE_DATA_API] = runtime

    coordinator = TibberDataAPICoordinator(hass, data_api_entry, runtime)
    data_api_entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)

    with pytest.raises(ConfigEntryNotReady):
        await coordinator.async_config_entry_first_refresh()
    assert isinstance(coordinator.last_exception, UpdateFailed)


async def test_data_api_coordinator_first_refresh_auth_failed(
    hass: HomeAssistant, data_api_entry: MockConfigEntry
) -> None:
    """Ensure auth failures during setup propagate."""
    runtime = MagicMock()
    runtime.async_get_client = AsyncMock(side_effect=ConfigEntryAuthFailed("invalid"))
    hass.data.setdefault(DOMAIN, {})[API_TYPE_DATA_API] = runtime

    coordinator = TibberDataAPICoordinator(hass, data_api_entry, runtime)
    data_api_entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator.async_config_entry_first_refresh()


@pytest.mark.parametrize(
    "exception",
    [
        (aiohttp.ClientError("err"),),
        (TimeoutError(),),
        (tibber.UserAgentMissingError("err"),),
    ],
)
async def test_data_api_coordinator_update_failures(
    hass: HomeAssistant, data_api_entry: MockConfigEntry, exception: tuple[Exception]
) -> None:
    """Ensure update failures are wrapped in UpdateFailed."""
    runtime = MagicMock()
    (side_effect,) = exception
    runtime.async_get_client = AsyncMock(side_effect=side_effect)
    hass.data.setdefault(DOMAIN, {})[API_TYPE_DATA_API] = runtime

    coordinator = TibberDataAPICoordinator(hass, data_api_entry, runtime)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
