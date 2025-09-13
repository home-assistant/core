"""Test the vitrea cover platform."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.vitrea.cover import VitreaCover
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_cover_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test cover entities are created and handled properly."""
    # Create a test cover entity
    cover = VitreaCover(node="01", key="01", position="050", monitor=mock_vitrea_client)

    # Test initial state
    assert cover.unique_id == "01_01"
    assert cover.name == "Blind 01"
    assert cover.current_cover_position == 50
    assert not cover.is_closed
    assert not cover.is_open
    assert cover.assumed_state is True
    assert cover.should_poll is False


async def test_cover_open(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test cover opening."""
    cover = VitreaCover(node="01", key="01", position="000", monitor=mock_vitrea_client)

    await cover.async_open_cover()

    mock_vitrea_client.blind_open.assert_called_once_with("01", "01")
    assert cover.current_cover_position == 100


async def test_cover_close(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test cover closing."""
    cover = VitreaCover(node="01", key="01", position="100", monitor=mock_vitrea_client)

    await cover.async_close_cover()

    mock_vitrea_client.blind_close.assert_called_once_with("01", "01")
    assert cover.current_cover_position == 0


async def test_cover_set_position(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test setting cover position."""
    cover = VitreaCover(node="01", key="01", position="000", monitor=mock_vitrea_client)

    await cover.async_set_cover_position(position=75)

    mock_vitrea_client.blind_percent.assert_called_once_with("01", "01", 75)
    assert cover.current_cover_position == 75


def test_cover_set_position_sync(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test setting cover position synchronously."""
    cover = VitreaCover(node="01", key="01", position="000", monitor=mock_vitrea_client)

    cover.set_position(30)

    assert cover.current_cover_position == 30
    assert cover._target_position == 30
    assert cover._initial_position == 30
    assert not cover._is_opening
    assert not cover._is_closing


async def test_cover_stop(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test stopping cover movement."""
    cover = VitreaCover(node="01", key="01", position="050", monitor=mock_vitrea_client)

    await cover.async_stop_cover()

    mock_vitrea_client.blind_stop.assert_called_once_with("01", "01")


async def test_cover_device_info(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test cover device info is set correctly."""
    cover = VitreaCover(node="01", key="01", position="050", monitor=mock_vitrea_client)

    device_info = cover.device_info
    assert device_info is not None
    assert device_info["identifiers"] == {("vitrea", "01")}
    assert device_info["name"] == "Node 01"
    assert device_info["manufacturer"] == "Vitrea"


# test OSError and TimeoutError handling in open, close, set_position, stop methods
async def test_cover_open_error_handling(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test error handling in cover opening."""
    cover = VitreaCover(node="01", key="01", position="000", monitor=mock_vitrea_client)

    mock_vitrea_client.blind_open.side_effect = OSError("Connection error")

    await cover.async_open_cover()

    mock_vitrea_client.blind_open.assert_called_once_with("01", "01")
    assert cover.current_cover_position == 0
    mock_vitrea_client.blind_open.reset_mock()
    mock_vitrea_client.blind_open.side_effect = TimeoutError("Timeout error")
    await cover.async_open_cover()
    mock_vitrea_client.blind_open.assert_called_once_with("01", "01")
    assert cover.current_cover_position == 0


async def test_cover_close_error_handling(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test error handling in cover closing."""
    cover = VitreaCover(node="01", key="01", position="100", monitor=mock_vitrea_client)

    mock_vitrea_client.blind_close.side_effect = OSError("Connection error")

    await cover.async_close_cover()

    mock_vitrea_client.blind_close.assert_called_once_with("01", "01")
    assert cover.current_cover_position == 100
    mock_vitrea_client.blind_close.reset_mock()
    mock_vitrea_client.blind_close.side_effect = TimeoutError("Timeout error")
    await cover.async_close_cover()
    mock_vitrea_client.blind_close.assert_called_once_with("01", "01")
    assert cover.current_cover_position == 100


async def test_cover_set_position_error_handling(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test error handling in setting cover position."""
    cover = VitreaCover(node="01", key="01", position="000", monitor=mock_vitrea_client)

    mock_vitrea_client.blind_percent.side_effect = OSError("Connection error")

    await cover.async_set_cover_position(position=75)

    mock_vitrea_client.blind_percent.assert_called_once_with("01", "01", 75)
    assert cover.current_cover_position == 0
    mock_vitrea_client.blind_percent.reset_mock()
    mock_vitrea_client.blind_percent.side_effect = TimeoutError("Timeout error")
    await cover.async_set_cover_position(position=75)
    mock_vitrea_client.blind_percent.assert_called_once_with("01", "01", 75)
    assert cover.current_cover_position == 0  # Position is set optimistically


async def test_cover_stop_error_handling(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test error handling in stopping cover movement."""
    cover = VitreaCover(node="01", key="01", position="050", monitor=mock_vitrea_client)

    mock_vitrea_client.blind_stop.side_effect = OSError("Connection error")

    await cover.async_stop_cover()

    mock_vitrea_client.blind_stop.assert_called_once_with("01", "01")
    # No exception should be raised, error is logged
    mock_vitrea_client.blind_stop.reset_mock()
    mock_vitrea_client.blind_stop.side_effect = TimeoutError("Timeout error")
    await cover.async_stop_cover()


async def test_async_set_cover_position_missing_position(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test set_cover_position with missing position argument."""
    cover = VitreaCover(node="01", key="01", position="050", monitor=mock_vitrea_client)
    with patch("homeassistant.components.vitrea.cover._LOGGER") as mock_logger:
        await cover.async_set_cover_position()
        mock_logger.error.assert_called_once_with(
            "Cover_position missing POSITION value"
        )
