"""Test the Airobot integration init."""

from unittest.mock import AsyncMock

from pyairobotrest.exceptions import AirobotAuthError, AirobotConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.airobot.const import DOMAIN
from homeassistant.components.airobot.entity import AirobotEntity
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("init_integration")
async def test_setup_entry_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful setup of a config entry."""
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (AirobotAuthError("Authentication failed"), ConfigEntryState.SETUP_ERROR),
        (AirobotConnectionError("Connection failed"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_entry_exceptions(
    hass: HomeAssistant,
    mock_airobot_client: AsyncMock,
    mock_airobot_config_flow_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup fails with various exceptions."""
    mock_config_entry.add_to_hass(hass)

    mock_airobot_client.get_statuses.side_effect = exception

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


@pytest.mark.usefixtures("init_integration")
async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test unloading a config entry."""
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("init_integration")
async def test_coordinator_update_failed(
    hass: HomeAssistant,
    mock_airobot_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles update failures."""
    # Simulate connection error during update
    mock_airobot_client.get_statuses.side_effect = AirobotConnectionError(
        "Connection lost"
    )

    coordinator = mock_config_entry.runtime_data
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False


@pytest.mark.usefixtures("init_integration")
async def test_coordinator_update_recovery(
    hass: HomeAssistant,
    mock_airobot_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test coordinator logs when device recovers from unavailability."""
    coordinator = mock_config_entry.runtime_data

    # Simulate connection error to make device unavailable
    mock_airobot_client.get_statuses.side_effect = AirobotConnectionError(
        "Connection lost"
    )
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False
    assert "Device is unavailable" in caplog.text

    # Clear the log
    caplog.clear()

    # Restore connection - device comes back online
    mock_airobot_client.get_statuses.side_effect = None
    await coordinator.async_refresh()
    assert coordinator.last_update_success is True
    assert "Device is back online" in caplog.text


@pytest.mark.usefixtures("init_integration")
async def test_device_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device registry entry."""
    assert (
        device_entry := device_registry.async_get_device(
            identifiers={(DOMAIN, "T01XXXXXX")}
        )
    )
    assert device_entry == snapshot


@pytest.mark.usefixtures("init_integration")
async def test_entity_with_entity_key(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entity initialization with entity_key parameter."""
    coordinator = mock_config_entry.runtime_data

    # Create entity with entity_key to test that code path
    entity = AirobotEntity(coordinator, entity_key="test_sensor")

    # Verify unique_id includes entity_key
    assert entity.unique_id == "T01XXXXXX_test_sensor"

    # Create entity without entity_key
    entity_no_key = AirobotEntity(coordinator)

    # Verify unique_id is just device_id
    assert entity_no_key.unique_id == "T01XXXXXX"
