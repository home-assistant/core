"""Tests for the LoJack integration setup."""

from unittest.mock import AsyncMock, MagicMock, patch

from lojack_api import ApiError, AuthenticationError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lojack.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .const import TEST_DEVICE_ID

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: MagicMock,
) -> None:
    """Test successful setup of the integration."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("device_tracker.2021_honda_accord") is not None


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (AuthenticationError("Invalid credentials"), ConfigEntryState.SETUP_ERROR),
        (ApiError("Connection failed"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_entry_create_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup failure when LoJackClient.create raises an error."""
    with patch(
        "homeassistant.components.lojack.LoJackClient.create",
        side_effect=side_effect,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (AuthenticationError("Invalid credentials"), ConfigEntryState.SETUP_ERROR),
        (ApiError("Connection failed"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_entry_list_devices_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: MagicMock,
    side_effect: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup failure when list_devices raises an error."""
    mock_lojack_client.list_devices = AsyncMock(side_effect=side_effect)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


async def test_setup_entry_no_vehicles(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: MagicMock,
) -> None:
    """Test integration loads successfully with no vehicles."""
    mock_lojack_client.list_devices = AsyncMock(return_value=[])

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(hass.states.async_entity_ids("device_tracker")) == 0


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: MagicMock,
) -> None:
    """Test successful unload of the integration."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_reload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: MagicMock,
) -> None:
    """Test integration reloads successfully."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device registry entry is created."""
    await setup_integration(hass, mock_config_entry)

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_DEVICE_ID)}
    )
    assert device_entry is not None
    assert device_entry == snapshot
