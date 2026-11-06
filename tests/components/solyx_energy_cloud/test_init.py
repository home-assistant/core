"""Tests for the Solyx Energy integration setup and unload.

These drive the real HA config-entry lifecycle (setup, unload, retry)
with the API client mocked at the class level, so no network calls are made.
"""

from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from solyx_energy_api.exceptions import SolyxEnergyDataError, SolyxEnergyTokenError

from homeassistant.components.solyx_energy_cloud.const import (
    DATA_INTERVAL_SECONDS,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE

from .const import NYMO_DEVICE_ID, NYMO_DEVICE_ID_2

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.device_registry import DeviceRegistry
    from homeassistant.helpers.entity_registry import EntityRegistry


async def test_load_unload_config_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The integration loads and can be unloaded cleanly."""
    assert init_integration.state is ConfigEntryState.LOADED
    assert set(init_integration.runtime_data.data) == {NYMO_DEVICE_ID, NYMO_DEVICE_ID_2}

    # Unload and confirm HA marks the entry as no longer loaded.
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()
    assert init_integration.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "api_error",
    [
        pytest.param(SolyxEnergyTokenError(), id="token_error"),
        pytest.param(SolyxEnergyDataError(), id="data_error"),
    ],
)
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client_class: AsyncMock,
    api_error: Exception,
) -> None:
    """An API error occurs (translates to UpdateFailed) and schedules a retry (SETUP_RETRY) instead of hard-failing the entry."""
    mock_api_client_class.async_get_assets.side_effect = api_error

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "device_id",
    [
        pytest.param(NYMO_DEVICE_ID, id="nymo"),
        pytest.param(NYMO_DEVICE_ID_2, id="nymo_2"),
    ],
)
async def test_device_info(
    device_registry: DeviceRegistry,
    init_integration: MockConfigEntry,
    device_id: str,
) -> None:
    """Setup registers every Nymo device in HA's device registry with the right info."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, device_id), init_integration.entry_id
    )
    assert device is not None
    assert device.manufacturer == "Solyx Energy"
    assert device.model == "Nymo"
    assert device.name == "Nymo"
    assert device.serial_number == device_id


async def test_device_added_dynamically(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: DeviceRegistry,
    entity_registry: EntityRegistry,
    mock_api_client_class: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A device that appears in the API response after setup is added automatically."""
    assets = mock_api_client_class.async_get_assets.return_value
    mock_api_client_class.async_get_assets.return_value = assets[:1]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, NYMO_DEVICE_ID_2), mock_config_entry.entry_id
        )
        is None
    )

    mock_api_client_class.async_get_assets.return_value = assets
    freezer.tick(timedelta(seconds=DATA_INTERVAL_SECONDS + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, NYMO_DEVICE_ID_2), mock_config_entry.entry_id
        )
        is not None
    )
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{NYMO_DEVICE_ID_2}-boiler_power"
    )
    assert entity_id is not None

    mock_api_client_class.async_get_assets.return_value = assets[:1]
    freezer.tick(timedelta(seconds=DATA_INTERVAL_SECONDS + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
