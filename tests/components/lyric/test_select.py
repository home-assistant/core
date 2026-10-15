"""Tests for the Honeywell Lyric select platform."""

from typing import Any
from unittest.mock import MagicMock, patch

from aiolyric.objects.priority import LyricPriority
import pytest

from homeassistant.components.lyric.const import DOMAIN
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import LCC_SUPPORTED_MAC, lyric_exception

from tests.common import MockConfigEntry

LCC_UNIQUE_ID = f"{LCC_SUPPORTED_MAC}_room_priority"


@pytest.mark.usefixtures("setup_credentials", "mock_lyric_mixed_devices")
async def test_room_priority_select_created_regardless_of_device_id_prefix(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """The room priority select is created regardless of device ID prefix."""
    with patch("homeassistant.components.lyric.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    lcc_select = hass.states.get(
        entity_registry.async_get_entity_id(
            Platform.SELECT, DOMAIN, "AABBCC000001_room_priority"
        )
    )
    assert lcc_select.attributes["options"] == ["follow_me", "Living Room"]

    non_lcc_select = hass.states.get(
        entity_registry.async_get_entity_id(
            Platform.SELECT, DOMAIN, "AABBCC000002_room_priority"
        )
    )
    assert non_lcc_select.attributes["options"] == ["follow_me", "Office"]

    assert (
        entity_registry.async_get_entity_id(
            Platform.SELECT, DOMAIN, "AABBCC000003_room_priority"
        )
        is None
    )


async def _setup_select(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> str:
    """Set up the select platform and return the LCC room priority entity ID."""
    with patch("homeassistant.components.lyric.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)
    entity_id = entity_registry.async_get_entity_id(
        Platform.SELECT, DOMAIN, LCC_UNIQUE_ID
    )
    assert entity_id
    return entity_id


@pytest.mark.parametrize(
    ("priority", "expected_state"),
    [
        pytest.param(
            {"priorityType": "FollowMe", "selectedRooms": []},
            "follow_me",
            id="follow_me",
        ),
        pytest.param(
            {"priorityType": "PickARoom", "selectedRooms": [0]},
            "Living Room",
            id="pick_a_room",
        ),
        pytest.param(
            {"priorityType": "PickARoom", "selectedRooms": []},
            STATE_UNKNOWN,
            id="pick_a_room_no_selection",
        ),
        pytest.param(
            {"priorityType": "PickARoom", "selectedRooms": [5]},
            STATE_UNKNOWN,
            id="pick_a_room_unknown_room",
        ),
        pytest.param(
            {"priorityType": "WholeHouse", "selectedRooms": []},
            STATE_UNKNOWN,
            id="whole_house",
        ),
    ],
)
@pytest.mark.usefixtures("setup_credentials")
async def test_room_priority_current_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_lyric_mixed_devices: MagicMock,
    priority: dict[str, Any],
    expected_state: str,
) -> None:
    """The current option reflects the thermostat's room priority."""
    mock_lyric_mixed_devices.priorities_dict[LCC_SUPPORTED_MAC] = LyricPriority(
        {"priority": priority}
    )

    entity_id = await _setup_select(hass, mock_config_entry, entity_registry)

    assert hass.states.get(entity_id).state == expected_state


@pytest.mark.parametrize(
    ("option", "priority_type", "rooms"),
    [
        pytest.param("follow_me", "FollowMe", [], id="follow_me"),
        pytest.param("Living Room", "PickARoom", [0], id="pick_a_room"),
    ],
)
@pytest.mark.usefixtures("setup_credentials")
async def test_room_priority_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_lyric_mixed_devices: MagicMock,
    option: str,
    priority_type: str,
    rooms: list[int],
) -> None:
    """Selecting an option sets the room priority and refreshes."""
    entity_id = await _setup_select(hass, mock_config_entry, entity_registry)
    mock_lyric_mixed_devices.get_locations.reset_mock()

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
        blocking=True,
    )

    mock_lyric_mixed_devices.update_priority.assert_awaited_once()
    _, kwargs = mock_lyric_mixed_devices.update_priority.call_args
    assert kwargs == {"priority_type": priority_type, "rooms": rooms}
    mock_lyric_mixed_devices.get_locations.assert_awaited_once()


@pytest.mark.usefixtures("setup_credentials")
async def test_room_priority_select_option_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_lyric_mixed_devices: MagicMock,
) -> None:
    """An API error when setting the room priority is raised as a translated error."""
    entity_id = await _setup_select(hass, mock_config_entry, entity_registry)
    mock_lyric_mixed_devices.update_priority.side_effect = lyric_exception(500)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "follow_me"},
            blocking=True,
        )

    assert exc_info.value.translation_key == "failed_to_set_room_priority"
