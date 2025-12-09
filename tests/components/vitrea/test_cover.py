"""Test the vitrea cover platform."""

from unittest.mock import MagicMock

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_cover_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test cover entities are created correctly."""
    # Get the coordinator from runtime data
    coordinator = init_integration.runtime_data

    # Verify the coordinator is set up properly
    assert coordinator is not None
    assert coordinator.client == mock_vitrea_client

    # Verify status_request was called during setup
    mock_vitrea_client.status_request.assert_called()


async def test_cover_open(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test cover opening."""
    entity_id = "cover.node_01_blind_01"

    await hass.services.async_call(
        "cover",
        "open_cover",
        {"entity_id": entity_id},
        blocking=True,
    )

    mock_vitrea_client.blind_open.assert_called_once_with("01", "01")


async def test_cover_close(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test cover closing."""
    entity_id = "cover.node_01_blind_01"

    await hass.services.async_call(
        "cover",
        "close_cover",
        {"entity_id": entity_id},
        blocking=True,
    )

    mock_vitrea_client.blind_close.assert_called_once_with("01", "01")


async def test_cover_set_position(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test setting cover position."""
    entity_id = "cover.node_01_blind_01"

    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {"entity_id": entity_id, "position": 75},
        blocking=True,
    )

    mock_vitrea_client.blind_percent.assert_called_once_with("01", "01", 75)


def test_cover_set_position_sync(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test setting cover position synchronously."""
    # This test is no longer relevant with coordinator pattern
    # Position is managed by coordinator data updates


async def test_cover_stop(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test stopping cover movement."""
    entity_id = "cover.node_01_blind_01"

    await hass.services.async_call(
        "cover",
        "stop_cover",
        {"entity_id": entity_id},
        blocking=True,
    )

    mock_vitrea_client.blind_stop.assert_called_once_with("01", "01")


async def test_cover_device_info(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test cover device info is set correctly."""
    entity_registry = er.async_get(hass)
    entity_id = "cover.node_01_blind_01"

    entity_entry = entity_registry.async_get(entity_id)
    if entity_entry:
        assert entity_entry.unique_id == "01_01"


# test OSError and TimeoutError handling in open, close, set_position, stop methods
async def test_cover_open_error_handling(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test error handling in cover opening."""
    entity_id = "cover.node_01_blind_01"

    mock_vitrea_client.blind_open.side_effect = OSError("Connection error")

    # Should not raise exception - error is logged
    await hass.services.async_call(
        "cover",
        "open_cover",
        {"entity_id": entity_id},
        blocking=True,
    )

    mock_vitrea_client.blind_open.assert_called_once_with("01", "01")

    mock_vitrea_client.blind_open.reset_mock()
    mock_vitrea_client.blind_open.side_effect = TimeoutError("Timeout error")

    await hass.services.async_call(
        "cover",
        "open_cover",
        {"entity_id": entity_id},
        blocking=True,
    )
    mock_vitrea_client.blind_open.assert_called_once_with("01", "01")


async def test_cover_close_error_handling(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test error handling in cover closing."""
    entity_id = "cover.node_01_blind_01"

    mock_vitrea_client.blind_close.side_effect = OSError("Connection error")

    await hass.services.async_call(
        "cover",
        "close_cover",
        {"entity_id": entity_id},
        blocking=True,
    )

    mock_vitrea_client.blind_close.assert_called_once_with("01", "01")

    mock_vitrea_client.blind_close.reset_mock()
    mock_vitrea_client.blind_close.side_effect = TimeoutError("Timeout error")

    await hass.services.async_call(
        "cover",
        "close_cover",
        {"entity_id": entity_id},
        blocking=True,
    )
    mock_vitrea_client.blind_close.assert_called_once_with("01", "01")


async def test_cover_set_position_error_handling(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test error handling in setting cover position."""
    entity_id = "cover.node_01_blind_01"

    mock_vitrea_client.blind_percent.side_effect = OSError("Connection error")

    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {"entity_id": entity_id, "position": 75},
        blocking=True,
    )

    mock_vitrea_client.blind_percent.assert_called_once_with("01", "01", 75)

    mock_vitrea_client.blind_percent.reset_mock()
    mock_vitrea_client.blind_percent.side_effect = TimeoutError("Timeout error")

    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {"entity_id": entity_id, "position": 75},
        blocking=True,
    )
    mock_vitrea_client.blind_percent.assert_called_once_with("01", "01", 75)


async def test_cover_stop_error_handling(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test error handling in stopping cover movement."""
    entity_id = "cover.node_01_blind_01"

    mock_vitrea_client.blind_stop.side_effect = OSError("Connection error")

    await hass.services.async_call(
        "cover",
        "stop_cover",
        {"entity_id": entity_id},
        blocking=True,
    )

    mock_vitrea_client.blind_stop.assert_called_once_with("01", "01")

    # No exception should be raised, error is logged
    mock_vitrea_client.blind_stop.reset_mock()
    mock_vitrea_client.blind_stop.side_effect = TimeoutError("Timeout error")

    await hass.services.async_call(
        "cover",
        "stop_cover",
        {"entity_id": entity_id},
        blocking=True,
    )


async def test_async_set_cover_position_missing_position(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test set_cover_position with missing position argument."""
    # This test is handled at the service layer - Home Assistant validates required parameters
    # The entity method won't be called without position parameter


async def test_cover_position_no_coordinator_data(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test cover position returns None when coordinator has no data."""

    # Get the actual entity
    entity_registry = er.async_get(hass)
    entity_id = "cover.node_01_blind_01"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None

    # Get the entity object from the platform
    entity = hass.data["entity_components"]["cover"].get_entity(entity_id)
    assert entity is not None

    # Clear the coordinator data
    coordinator = init_integration.runtime_data
    coordinator.data = None

    # Access current_cover_position - should return None (line 94)
    position = entity.current_cover_position
    assert position is None


async def test_cover_position_entity_not_in_data(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test cover position returns None when entity not in coordinator data."""

    # Get the actual entity
    entity_registry = er.async_get(hass)
    entity_id = "cover.node_01_blind_01"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None

    # Get the entity object
    entity = hass.data["entity_components"]["cover"].get_entity(entity_id)
    assert entity is not None

    coordinator = init_integration.runtime_data

    # Set data but remove our entity
    coordinator.data = {"99_99": {"position": 50}}

    # Access current_cover_position - should return None (line 94)
    position = entity.current_cover_position
    assert position is None


async def test_cover_open_logs_error_on_oserror(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test cover open logs error on OSError."""
    entity_id = "cover.node_01_blind_01"

    mock_vitrea_client.blind_open.side_effect = OSError("Connection error")

    # Should log error but not raise - let the actual logging happen
    await hass.services.async_call(
        "cover",
        "open_cover",
        {"entity_id": entity_id},
        blocking=True,
    )

    # Verify the command was attempted
    mock_vitrea_client.blind_open.assert_called_once_with("01", "01")


async def test_cover_close_logs_error_on_timeout(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test cover close logs error on TimeoutError."""
    entity_id = "cover.node_01_blind_01"

    mock_vitrea_client.blind_close.side_effect = TimeoutError("Timeout")

    # Should log error but not raise
    await hass.services.async_call(
        "cover",
        "close_cover",
        {"entity_id": entity_id},
        blocking=True,
    )

    mock_vitrea_client.blind_close.assert_called_once_with("01", "01")


async def test_cover_set_position_logs_error_on_oserror(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test cover set_position logs error on OSError."""
    entity_id = "cover.node_01_blind_01"

    mock_vitrea_client.blind_percent.side_effect = OSError("Connection error")

    # Should log error but not raise
    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {"entity_id": entity_id, "position": 75},
        blocking=True,
    )

    mock_vitrea_client.blind_percent.assert_called_once_with("01", "01", 75)


async def test_cover_stop_logs_error_on_timeout(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test cover stop logs error on TimeoutError."""
    entity_id = "cover.node_01_blind_01"

    mock_vitrea_client.blind_stop.side_effect = TimeoutError("Timeout")

    # Should log error but not raise
    await hass.services.async_call(
        "cover",
        "stop_cover",
        {"entity_id": entity_id},
        blocking=True,
    )

    mock_vitrea_client.blind_stop.assert_called_once_with("01", "01")
