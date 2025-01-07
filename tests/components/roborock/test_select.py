"""Test Roborock Select platform."""

import copy
from unittest.mock import patch

import pytest
from roborock.exceptions import RoborockException

from homeassistant.components.roborock import DOMAIN
from homeassistant.const import SERVICE_SELECT_OPTION, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from .mock_data import MULTI_MAP_LIST, PROP

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("entity_id", "value"),
    [
        ("select.roborock_s7_maxv_mop_mode", "deep"),
        ("select.roborock_s7_maxv_mop_intensity", "mild"),
        ("select.roborock_s7_maxv_selected_map", "Downstairs"),
    ],
)
async def test_update_success(
    hass: HomeAssistant,
    bypass_api_fixture,
    setup_entry: MockConfigEntry,
    entity_id: str,
    value: str,
) -> None:
    """Test allowed changing values for select entities."""
    # Ensure that the entity exist, as these test can pass even if there is no entity.
    assert hass.states.get(entity_id) is not None
    with patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.send_message"
    ) as mock_send_message:
        await hass.services.async_call(
            "select",
            SERVICE_SELECT_OPTION,
            service_data={"option": value},
            blocking=True,
            target={"entity_id": entity_id},
        )
    assert mock_send_message.assert_called_once


async def test_update_failure(
    hass: HomeAssistant,
    bypass_api_fixture,
    setup_entry: MockConfigEntry,
) -> None:
    """Test that changing a value will raise a homeassistanterror when it fails."""
    with (
        patch(
            "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.send_message",
            side_effect=RoborockException(),
        ),
        pytest.raises(HomeAssistantError, match="Error while calling SET_MOP_MOD"),
    ):
        await hass.services.async_call(
            "select",
            SERVICE_SELECT_OPTION,
            service_data={"option": "deep"},
            blocking=True,
            target={"entity_id": "select.roborock_s7_maxv_mop_mode"},
        )


async def test_none_map_select(
    hass: HomeAssistant,
    bypass_api_fixture,
    mock_roborock_entry: MockConfigEntry,
) -> None:
    """Test that the select entity correctly handles not having a current map."""
    prop = copy.deepcopy(PROP)
    # Set map status to None so that current map is never set
    prop.status.map_status = None
    with patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.get_prop",
        return_value=prop,
    ):
        await async_setup_component(hass, DOMAIN, {})
    select_entity = hass.states.get("select.roborock_s7_maxv_selected_map")
    assert select_entity.state == STATE_UNKNOWN


async def test_selected_map_name(
    hass: HomeAssistant,
    bypass_api_fixture,
    mock_roborock_entry: MockConfigEntry,
) -> None:
    """Test that the selected map is set to the correct map name."""
    await async_setup_component(hass, DOMAIN, {})
    select_entity = hass.states.get("select.roborock_s7_maxv_selected_map")
    assert select_entity.state == "Upstairs"


async def test_selected_map_without_name(
    hass: HomeAssistant,
    bypass_api_fixture_v1_only,
    mock_roborock_entry: MockConfigEntry,
) -> None:
    """Test that maps without a name are given a placeholder name."""
    map_list = copy.deepcopy(MULTI_MAP_LIST)
    map_list.map_info[0].name = ""
    with patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.get_multi_maps_list",
        return_value=map_list,
    ):
        await async_setup_component(hass, DOMAIN, {})

    select_entity = hass.states.get("select.roborock_s7_maxv_selected_map")
    assert select_entity
    assert select_entity.state == "Map 0"
