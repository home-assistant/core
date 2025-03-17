"""Test homee covers."""

from unittest.mock import MagicMock

import pytest
from websockets import frames
from websockets.exceptions import ConnectionClosed

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN as COVER_DOMAIN,
    CoverEntityFeature,
    CoverState,
)
from homeassistant.components.homee.const import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import build_mock_node, setup_integration

from tests.common import MockConfigEntry


async def test_open_close_stop_cover(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test opening the cover."""
    mock_homee.nodes = [build_mock_node("cover_with_position_slats.json")]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: "cover.test_cover"},
        blocking=True,
    )
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: "cover.test_cover"},
        blocking=True,
    )
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: "cover.test_cover"},
        blocking=True,
    )

    calls = mock_homee.set_value.call_args_list
    for index, call in enumerate(calls):
        assert call[0] == (mock_homee.nodes[0].id, 1, index)


async def test_set_cover_position(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting the cover position."""
    mock_homee.nodes = [build_mock_node("cover_with_position_slats.json")]

    await setup_integration(hass, mock_config_entry)

    # Slats have a range of -45 to 90.
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.test_slats", ATTR_POSITION: 100},
        blocking=True,
    )
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.test_slats", ATTR_POSITION: 0},
        blocking=True,
    )
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.test_slats", ATTR_POSITION: 50},
        blocking=True,
    )

    calls = mock_homee.set_value.call_args_list
    positions = [0, 100, 50]
    for call in calls:
        assert call[0] == (1, 2, positions.pop(0))


async def test_close_open_slats(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test closing and opening slats."""
    mock_homee.nodes = [build_mock_node("cover_with_slats_position.json")]

    await setup_integration(hass, mock_config_entry)

    attributes = hass.states.get("cover.test_slats").attributes
    assert attributes.get("supported_features") == (
        CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.CLOSE_TILT
        | CoverEntityFeature.SET_TILT_POSITION
    )

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.test_slats"},
        blocking=True,
    )
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.test_slats"},
        blocking=True,
    )

    calls = mock_homee.set_value.call_args_list
    for index, call in enumerate(calls, start=1):
        assert call[0] == (mock_homee.nodes[0].id, 2, index)


async def test_set_slat_position(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting slats position."""
    mock_homee.nodes = [build_mock_node("cover_with_slats_position.json")]

    await setup_integration(hass, mock_config_entry)

    # Slats have a range of -45 to 90 on this device.
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: "cover.test_slats", ATTR_TILT_POSITION: 100},
        blocking=True,
    )
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: "cover.test_slats", ATTR_TILT_POSITION: 0},
        blocking=True,
    )
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: "cover.test_slats", ATTR_TILT_POSITION: 50},
        blocking=True,
    )

    calls = mock_homee.set_value.call_args_list
    positions = [-45, 90, 22.5]
    for call in calls:
        assert call[0] == (1, 1, positions.pop(0))


async def test_cover_positions(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an open cover."""
    # Cover open, tilt open.
    # mock_homee.nodes = [cover]
    mock_homee.nodes = [build_mock_node("cover_with_position_slats.json")]
    cover = mock_homee.nodes[0]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("cover.test_cover").state == CoverState.OPEN

    attributes = hass.states.get("cover.test_cover").attributes
    assert attributes.get("supported_features") == (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_TILT_POSITION
    )
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
    cover.attributes[2].current_value = 56
    cover.add_on_changed_listener.call_args_list[0][0][0](cover)
    await hass.async_block_till_done()

    assert hass.states.get("cover.test_cover").state == CoverState.OPENING
    attributes = hass.states.get("cover.test_cover").attributes
    assert attributes.get("current_position") == 25
    assert attributes.get("current_tilt_position") == 25

    cover.attributes[0].current_value = 4
    cover.attributes[1].current_value = 25
    cover.attributes[2].current_value = -11
    cover.add_on_changed_listener.call_args_list[0][0][0](cover)
    await hass.async_block_till_done()

    assert hass.states.get("cover.test_cover").state == CoverState.CLOSING
    attributes = hass.states.get("cover.test_cover").attributes
    assert attributes.get("current_position") == 75
    assert attributes.get("current_tilt_position") == 74


async def test_reversed_cover(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a cover with inverted UP_DOWN attribute without position."""
    mock_homee.nodes = [build_mock_node("cover_without_position.json")]
    cover = mock_homee.nodes[0]

    await setup_integration(hass, mock_config_entry)

    cover.attributes[0].is_reversed = True
    cover.add_on_changed_listener.call_args_list[0][0][0](cover)
    await hass.async_block_till_done()

    attributes = hass.states.get("cover.test_cover").attributes
    assert attributes.get("supported_features") == (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )
    assert hass.states.get("cover.test_cover").state == CoverState.OPEN

    cover.attributes[0].current_value = 0
    cover.add_on_changed_listener.call_args_list[0][0][0](cover)
    await hass.async_block_till_done()

    assert hass.states.get("cover.test_cover").state == CoverState.CLOSED


async def test_send_error(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test failed set_value command."""
    mock_homee.nodes = [build_mock_node("cover_without_position.json")]

    await setup_integration(hass, mock_config_entry)

    mock_homee.set_value.side_effect = ConnectionClosed(
        rcvd=frames.Close(1002, "Protocol Error"), sent=None
    )
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: "cover.test_cover"},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "connection_closed"
