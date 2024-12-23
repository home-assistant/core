"""Test homee covers."""

from unittest.mock import MagicMock

from pyHomee import HomeeNode

from homeassistant.components.homee.const import DOMAIN
from homeassistant.components.homee.cover import HomeeCover
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_object_fixture


async def test_cover_open(
    hass: HomeAssistant, mock_homee: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test an open cover."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = mock_homee

    # Cover open, tilt open.
    cover_json = load_json_object_fixture("cover1.json", DOMAIN)
    cover_node = HomeeNode(cover_json)
    cover1 = HomeeCover(cover_node, mock_config_entry)

    assert cover1.unique_id == "00055511EECC-3-101"

    assert cover1.state == "open"
    assert cover1.is_closed is False
    assert cover1.is_closing is False
    assert cover1.is_opening is False
    assert round(cover1.current_cover_position) == 100
    assert round(cover1.current_cover_tilt_position) == 100


async def test_cover_closed(
    hass: HomeAssistant, mock_homee: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test a closed cover."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = mock_homee

    # Cover closed, tilt closed.
    cover_json = load_json_object_fixture("cover2.json", DOMAIN)
    cover_node = HomeeNode(cover_json)
    cover2 = HomeeCover(cover_node, mock_config_entry)

    assert cover2.state == "closed"
    assert cover2.is_closed is True
    assert cover2.is_closing is False
    assert cover2.is_opening is False
    assert round(cover2.current_cover_position) == 0
    assert round(cover2.current_cover_tilt_position) == 0


async def test_cover_opening(
    hass: HomeAssistant, mock_homee: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test an opening cover."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = mock_homee

    # opening, 75% homee / 25% HA
    cover_json = load_json_object_fixture("cover3.json", DOMAIN)
    cover_node = HomeeNode(cover_json)
    cover3 = HomeeCover(cover_node, mock_config_entry)

    assert cover3.state == "opening"
    assert cover3.is_closed is False
    assert cover3.is_closing is False
    assert cover3.is_opening is True
    assert round(cover3.current_cover_position) == 25
    assert round(cover3.current_cover_tilt_position) == 25


async def test_cover_closing(
    hass: HomeAssistant, mock_homee: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test a closing cover."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = mock_homee

    # closing, 25% homee / 75% HA
    cover_json = load_json_object_fixture("cover4.json", DOMAIN)
    cover_node = HomeeNode(cover_json)
    cover4 = HomeeCover(cover_node, mock_config_entry)

    assert cover4.state == "closing"
    assert cover4.is_closed is False
    assert cover4.is_closing is True
    assert cover4.is_opening is False
    assert round(cover4.current_cover_position) == 75
    assert round(cover4.current_cover_tilt_position) == 75
