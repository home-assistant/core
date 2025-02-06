"""Test Suez_water integration initialization."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.suez_water.const import (
    CONF_COUNTER_ID,
    DATA_REFRESH_INTERVAL,
    DOMAIN,
)
from homeassistant.components.suez_water.coordinator import PySuezError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_USERNAME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from . import setup_integration
from .conftest import MOCK_CONTRACT, MOCK_DATA

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import WebSocketGenerator


async def test_initialization_invalid_credentials(
    hass: HomeAssistant,
    suez_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that suez_water can't be loaded with invalid credentials."""

    suez_client.check_credentials.return_value = False
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_initialization_setup_api_error(
    hass: HomeAssistant,
    suez_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that suez_water needs to retry loading if api failed to connect."""

    suez_client.check_credentials.side_effect = PySuezError("Test failure")
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_initialization_setup_device_error(
    hass: HomeAssistant,
    suez_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that suez_water needs to retry loading if api failed to connect."""

    suez_client.find_counter.side_effect = PySuezError("Test failure")
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_migration_version_rollback(
    hass: HomeAssistant,
    suez_client: AsyncMock,
) -> None:
    """Test that downgrading from a future version is not possible."""
    future_entry = MockConfigEntry(
        unique_id=MOCK_CONTRACT.fullRefFormat,
        domain=DOMAIN,
        title="Suez mock device",
        data=MOCK_DATA,
        version=3,
    )
    await setup_integration(hass, future_entry)
    assert future_entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_no_migration_current_version(
    hass: HomeAssistant,
    suez_client: AsyncMock,
) -> None:
    """Test that a current version does not migrate."""
    current_entry = MockConfigEntry(
        unique_id=MOCK_CONTRACT.fullRefFormat,
        domain=DOMAIN,
        title="Suez mock device",
        data=MOCK_DATA,
        version=2,
    )
    await setup_integration(hass, current_entry)
    assert current_entry.state is ConfigEntryState.LOADED
    assert current_entry.unique_id == MOCK_CONTRACT.fullRefFormat


async def test_migration_version_1_to_2_failure(
    hass: HomeAssistant,
    suez_client: AsyncMock,
) -> None:
    """Test that a migration from 1 to 2 changes the unique_id."""
    old_data = MOCK_DATA.copy()
    old_data[CONF_COUNTER_ID] = "12345"
    past_entry = MockConfigEntry(
        unique_id=old_data[CONF_USERNAME],
        domain=DOMAIN,
        title=old_data[CONF_USERNAME],
        data=old_data,
        version=1,
    )

    suez_client.contract_data.side_effect = PySuezError
    suez_client.contract_data.return_value = None
    await setup_integration(hass, past_entry)
    assert past_entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_migration_version_1_to_2_success(
    hass: HomeAssistant,
    suez_client: AsyncMock,
) -> None:
    """Test that a migration from 1 to 2 changes the unique_id."""
    old_data = MOCK_DATA.copy()
    old_data[CONF_COUNTER_ID] = "12345"
    past_entry = MockConfigEntry(
        unique_id=old_data[CONF_USERNAME],
        domain=DOMAIN,
        title=old_data[CONF_USERNAME],
        data=old_data,
        version=1,
    )

    await setup_integration(hass, past_entry)
    assert past_entry.state is ConfigEntryState.LOADED
    assert past_entry.unique_id == MOCK_CONTRACT.fullRefFormat
    assert past_entry.title == MOCK_DATA[CONF_USERNAME]
    assert past_entry.data
    assert past_entry.version == 2


async def test_remove_device(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    suez_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that we successfully remove an unknown device, but can't remove current one."""
    assert await async_setup_component(hass, "config", {})

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert mock_config_entry.supports_remove_device

    hass_client = await hass_ws_client(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "delete_this_device")},
    )
    assert device_entry

    response = await hass_client.remove_device(
        device_entry.id, mock_config_entry.entry_id
    )
    assert response["success"]

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "test-counter")},
    )
    assert device_entry
    response = await hass_client.remove_device(
        device_entry.id, mock_config_entry.entry_id
    )
    assert not response["success"]


async def test_new_device(
    hass: HomeAssistant,
    suez_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that we successfully remove an unknown device, but can't remove current one."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "test-counter")},
    )
    assert device_entry
    assert not device_entry.disabled

    suez_client.find_counter.side_effect = PySuezError
    suez_client.find_counter.return_value = None

    freezer.tick(DATA_REFRESH_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(True)

    entity_ids = await hass.async_add_executor_job(hass.states.entity_ids)
    for entity in entity_ids:
        state = hass.states.get(entity)
        assert entity
        assert state.state is STATE_UNAVAILABLE

    suez_client.find_counter.side_effect = None
    suez_client.find_counter.return_value = "new-counter"

    freezer.tick(DATA_REFRESH_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(True)

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "test-counter")},
    )
    assert not device_entry
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "new-counter")},
    )
    assert device_entry
