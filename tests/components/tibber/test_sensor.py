"""Tests for the Tibber Data API sensors and coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.recorder import Recorder
from homeassistant.components.tibber.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import create_tibber_device

from tests.common import MockConfigEntry


async def test_data_api_sensors_are_created(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    data_api_client_mock: AsyncMock,
    setup_credentials: None,
    entity_registry: er.EntityRegistry,
) -> None:
    """Ensure Data API sensors are created and expose values from the coordinator."""
    data_api_client_mock.get_all_devices = AsyncMock(
        return_value={"device-id": create_tibber_device(value=72.0)}
    )
    data_api_client_mock.update_devices = AsyncMock(
        return_value={"device-id": create_tibber_device(value=83.0)}
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    data_api_client_mock.get_all_devices.assert_awaited_once()
    data_api_client_mock.update_devices.assert_awaited_once()

    unique_id = "external-id_storage.stateOfCharge"
    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == 83.0
