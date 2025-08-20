"""Test the vitrea cover platform."""

from unittest.mock import MagicMock

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
