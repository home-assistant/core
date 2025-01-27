"""Test homee covers."""

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN, CoverState
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_CLOSE_COVER, SERVICE_OPEN_COVER
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_open_cover(
    hass: HomeAssistant,
    cover: AsyncMock,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test opening the cover."""
    mock_homee.nodes = [cover]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: "cover.test_cover"},
        blocking=True,
    )
    mock_homee.set_value.assert_called_once_with(cover.id, 1, 0)


async def test_close_cover(
    hass: HomeAssistant,
    cover: AsyncMock,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test opening the cover."""
    mock_homee.nodes = [cover]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: "cover.test_cover"},
        blocking=True,
    )

    mock_homee.set_value.assert_called_once_with(cover.id, 1, 1)


async def test_cover_positions(
    hass: HomeAssistant,
    cover: AsyncMock,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an open cover."""
    # Cover open, tilt open.
    mock_homee.nodes = [cover]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("cover.test_cover").state == CoverState.OPEN

    attributes = hass.states.get("cover.test_cover").attributes
    assert attributes.get("supported_features") == 143
    assert attributes.get("current_position") == 100
    assert attributes.get("current_tilt_position") == 100

    cover.attributes[0].current_value = 1
    cover.attributes[1].current_value = 100
    cover.attributes[2].current_value = 90
    cover.add_on_changed_listener.call_args_list[0][0][0](cover)
    await hass.async_block_till_done()

    attributes = hass.states.get("cover.test_cover").attributes
    assert attributes.get("current_position") == 0
    assert attributes.get("current_tilt_position") == 0
    assert hass.states.get("cover.test_cover").state == CoverState.CLOSED

    cover.attributes[0].current_value = 3
    cover.attributes[1].current_value = 75
    cover.attributes[2].current_value = 75
    cover.add_on_changed_listener.call_args_list[0][0][0](cover)
    await hass.async_block_till_done()

    assert hass.states.get("cover.test_cover").state == CoverState.OPENING
    attributes = hass.states.get("cover.test_cover").attributes
    assert attributes.get("current_position") == 25
    assert attributes.get("current_tilt_position") == 25

    cover.attributes[0].current_value = 4
    cover.attributes[1].current_value = 25
    cover.attributes[2].current_value = 25
    cover.add_on_changed_listener.call_args_list[0][0][0](cover)
    await hass.async_block_till_done()

    assert hass.states.get("cover.test_cover").state == CoverState.CLOSING
    attributes = hass.states.get("cover.test_cover").attributes
    assert attributes.get("current_position") == 75
    assert attributes.get("current_tilt_position") == 74
