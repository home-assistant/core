"""Test homee covers."""

from unittest.mock import AsyncMock, MagicMock

from pyHomee import HomeeNode

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN, CoverState
from homeassistant.components.homee.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_CLOSE_COVER, SERVICE_OPEN_COVER
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, load_json_object_fixture


async def test_cover_open(
    hass: HomeAssistant, mock_homee: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test an open cover."""
    # Cover open, tilt open.
    cover_json = load_json_object_fixture("cover1.json", DOMAIN)
    cover_node = HomeeNode(cover_json)
    mock_homee.nodes = [cover_node]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("cover.test_cover").state == CoverState.OPEN

    attributes = hass.states.get("cover.test_cover").attributes
    assert attributes.get("supported_features") == 143
    assert attributes.get("current_position") == 100
    assert attributes.get("current_tilt_position") == 100


async def test_cover_closed(
    hass: HomeAssistant, mock_homee: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test a closed cover."""
    # Cover closed, tilt closed.
    cover_json = load_json_object_fixture("cover2.json", DOMAIN)
    cover_node = HomeeNode(cover_json)
    mock_homee.nodes = [cover_node]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("cover.test_cover").state == CoverState.CLOSED
    attributes = hass.states.get("cover.test_cover").attributes
    assert attributes.get("current_position") == 0
    assert attributes.get("current_tilt_position") == 0


async def test_cover_opening(
    hass: HomeAssistant, mock_homee: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test an opening cover."""
    # opening, 75% homee / 25% HA
    cover_json = load_json_object_fixture("cover3.json", DOMAIN)
    cover_node = HomeeNode(cover_json)
    mock_homee.nodes = [cover_node]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("cover.test_cover").state == CoverState.OPENING
    attributes = hass.states.get("cover.test_cover").attributes
    assert attributes.get("current_position") == 25
    assert attributes.get("current_tilt_position") == 25


async def test_cover_closing(
    hass: HomeAssistant, mock_homee: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test a closing cover."""
    # closing, 25% homee / 75% HA
    cover_json = load_json_object_fixture("cover4.json", DOMAIN)
    cover_node = HomeeNode(cover_json)
    mock_homee.nodes = [cover_node]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("cover.test_cover").state == CoverState.CLOSING
    attributes = hass.states.get("cover.test_cover").attributes
    assert attributes.get("current_position") == 75
    assert attributes.get("current_tilt_position") == 74


async def test_open_cover(
    hass: HomeAssistant, mock_homee: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test opening the cover."""
    # Cover closed, tilt closed.
    cover_json = load_json_object_fixture("cover2.json", DOMAIN)
    cover_node = HomeeNode(cover_json)
    mock_homee.nodes = [cover_node]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: "cover.test_cover"},
        blocking=True,
    )
    mock_homee.set_value.assert_called_once_with(cover_node.id, 1, 0)


async def test_close_cover(
    hass: HomeAssistant, mock_homee: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test opening the cover."""
    # Cover open, tilt open.
    cover_json = load_json_object_fixture("cover1.json", DOMAIN)
    cover_node = HomeeNode(cover_json)
    mock_homee.nodes = [cover_node]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: "cover.test_cover"},
        blocking=True,
    )
    mock_homee.set_value.assert_called_once_with(cover_node.id, 1, 1)
