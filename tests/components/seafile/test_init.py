"""Test the Seafile integration setup and teardown."""

from unittest.mock import AsyncMock

from aioseafile import (
    SeafileAuthenticationError,
    SeafileConnectionError,
    SeafileTimeoutError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .conftest import SUBENTRY_ID


@pytest.mark.usefixtures("mock_seafile_client")
async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a config entry loads and unloads cleanly."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("method", "exception", "state"),
    [
        pytest.param(
            "get_libraries",
            SeafileConnectionError,
            ConfigEntryState.SETUP_RETRY,
            id="update_failed",
        ),
        pytest.param(
            "get_library",
            SeafileConnectionError,
            ConfigEntryState.SETUP_RETRY,
            id="library_details_failed",
        ),
        pytest.param(
            "get_libraries",
            SeafileTimeoutError,
            ConfigEntryState.SETUP_RETRY,
            id="timeout",
        ),
        pytest.param(
            "get_libraries",
            SeafileAuthenticationError,
            ConfigEntryState.SETUP_ERROR,
            id="token_revoked",
        ),
    ],
)
async def test_setup_failure(
    hass: HomeAssistant,
    mock_seafile_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    method: str,
    exception: type[Exception],
    state: ConfigEntryState,
) -> None:
    """Test setup failures are retried, except for a revoked token."""
    getattr(mock_seafile_client, method).side_effect = exception
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is state


@pytest.mark.usefixtures("mock_seafile_client")
async def test_remove_library(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test removing a library subentry removes its device and entities."""
    await setup_integration(hass, mock_config_entry)
    assert er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert hass.config_entries.async_remove_subentry(mock_config_entry, SUBENTRY_ID)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert hass.states.get("sensor.documents_size") is None
