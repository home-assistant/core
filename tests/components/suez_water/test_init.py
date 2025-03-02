"""Test Suez_water integration initialization."""

from unittest.mock import AsyncMock

from homeassistant.components.suez_water.const import CONF_COUNTER_ID, DOMAIN
from homeassistant.components.suez_water.coordinator import PySuezError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import MOCK_DATA

from tests.common import MockConfigEntry


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


async def test_migration_version_rollback(
    hass: HomeAssistant,
    suez_client: AsyncMock,
) -> None:
    """Test that downgrading from a future version is not possible."""
    future_entry = MockConfigEntry(
        unique_id=MOCK_DATA[CONF_COUNTER_ID],
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
        unique_id=MOCK_DATA[CONF_COUNTER_ID],
        domain=DOMAIN,
        title="Suez mock device",
        data=MOCK_DATA,
        version=2,
    )
    await setup_integration(hass, current_entry)
    assert current_entry.state is ConfigEntryState.LOADED
    assert current_entry.unique_id == MOCK_DATA[CONF_COUNTER_ID]


async def test_migration_version_1_to_2(
    hass: HomeAssistant,
    suez_client: AsyncMock,
) -> None:
    """Test that a migration from 1 to 2 changes the unique_id."""
    past_entry = MockConfigEntry(
        unique_id=MOCK_DATA[CONF_USERNAME],
        domain=DOMAIN,
        title=MOCK_DATA[CONF_USERNAME],
        data=MOCK_DATA,
        version=1,
    )

    await setup_integration(hass, past_entry)
    assert past_entry.state is ConfigEntryState.LOADED
    assert past_entry.unique_id == MOCK_DATA[CONF_COUNTER_ID]
    assert past_entry.title == MOCK_DATA[CONF_USERNAME]
    assert past_entry.version == 2
