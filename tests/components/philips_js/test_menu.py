"""Tests for the Philips TV menu setting entities and options."""

from unittest.mock import AsyncMock

from haphilipsjs import ConnectionFailure, GeneralFailure, PhilipsTV
import pytest

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.philips_js.const import CONF_ALLOW_NOTIFY, CONF_MENU_NODES
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError

from tests.common import MockConfigEntry

SLIDER_ID = 100
LIST_ID = 101
TOGGLE_ID = 102
MULTI_ID = 103
PARENT_ID = 104


def _node(node_id: int, node_type: str, context: str, data: dict) -> dict:
    return {
        "node_id": node_id,
        "type": node_type,
        "context": context,
        "string_id": f"string.{context}",
        "data": data,
    }


MOCK_MENU = {
    "node": {
        "node_id": 1,
        "type": "PARENT_NODE",
        "context": "Setup_Menu",
        "data": {
            "nodes": [
                _node(
                    SLIDER_ID,
                    "SLIDER_NODE",
                    "contrast",
                    {"slider_data": {"min": 0, "max": 100, "step_size": 1}},
                ),
                _node(
                    LIST_ID,
                    "LIST_NODE",
                    "eye_care",
                    {
                        "enums": [
                            {"enum_id": 0, "string_id": "string.off"},
                            {"enum_id": 1, "string_id": "string.on"},
                        ]
                    },
                ),
                _node(TOGGLE_ID, "TOGGLE_NODE", "toggle", {}),
                _node(
                    MULTI_ID,
                    "MULTIPLE_SLIDER",
                    "multi",
                    {
                        "sliders": [
                            {
                                "slider_id": "red",
                                "slider_data": {"min": 0, "max": 10},
                            }
                        ]
                    },
                ),
                _node(
                    PARENT_ID,
                    "PARENT_NODE",
                    "parent",
                    {
                        "nodes": [
                            {
                                "node_id": 200,
                                "type": "LEAF",
                                "string_id": "string.off",
                                "data": {},
                            },
                            {
                                "node_id": 201,
                                "type": "LEAF",
                                "string_id": "string.on",
                                "data": {},
                            },
                        ]
                    },
                ),
            ]
        },
    }
}

MOCK_VALUES = {
    SLIDER_ID: {
        "Nodeid": SLIDER_ID,
        "Available": True,
        "Controllable": True,
        "data": {"value": 70},
    },
    LIST_ID: {
        "Nodeid": LIST_ID,
        "Available": True,
        "Controllable": True,
        "data": {
            "selected_item": 1,
            "enum_values": [
                {"enum_id": 0, "available": True, "string_id": "string.off"},
                {"enum_id": 1, "available": True, "string_id": "string.on"},
            ],
        },
    },
    TOGGLE_ID: {
        "Nodeid": TOGGLE_ID,
        "Available": True,
        "Controllable": True,
        "data": {"value": False},
    },
    MULTI_ID: {
        "Nodeid": MULTI_ID,
        "Available": True,
        "Controllable": True,
        "data": {"values": [{"slider_id": "red", "value": 4}]},
    },
    PARENT_ID: {
        "Nodeid": PARENT_ID,
        "Available": True,
        "Controllable": True,
        "data": {"activenode_id": 201},
    },
}

STRINGS = {
    "string.contrast": "Contrast",
    "string.eye_care": "Eye care",
    "string.toggle": "Toggle",
    "string.off": "Off",
    "string.on": "On",
}


def _selected(node_ids: list[int]) -> list[dict]:
    nodes = {node["node_id"]: node for node in MOCK_MENU["node"]["data"]["nodes"]}
    return [{"node": nodes[node_id], "name": f"name {node_id}"} for node_id in node_ids]


@pytest.fixture(autouse=True)
def mock_menu(mock_tv: PhilipsTV) -> None:
    """Provide the menu of the TV."""
    mock_tv.settings = MOCK_MENU
    mock_tv.strings = STRINGS
    mock_tv.getStringsCached = AsyncMock(return_value=STRINGS)
    mock_tv.getMenuItemsSettingsCurrentValue = AsyncMock(
        side_effect=lambda node_ids: {
            node_id: MOCK_VALUES.get(node_id) for node_id in node_ids
        }
    )


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_options_flow_selects_nodes(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test selecting menu nodes in the options flow."""
    await _setup(hass, mock_config_entry)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ALLOW_NOTIFY: True, CONF_MENU_NODES: [str(SLIDER_ID)]},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[CONF_ALLOW_NOTIFY] is True
    assert [
        entry["node"]["node_id"] for entry in mock_config_entry.options[CONF_MENU_NODES]
    ] == [SLIDER_ID]


async def test_options_flow_menu_not_available(
    hass: HomeAssistant, mock_tv: PhilipsTV, mock_config_entry: MockConfigEntry
) -> None:
    """Test the options flow aborts if the menu of the TV is unknown."""
    mock_tv.settings = None
    await _setup(hass, mock_config_entry)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_selected_nodes_become_entities(
    hass: HomeAssistant, mock_tv: PhilipsTV, mock_config_entry: MockConfigEntry
) -> None:
    """Test the selected nodes are exposed and controllable."""
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={CONF_MENU_NODES: _selected([SLIDER_ID, LIST_ID, TOGGLE_ID])},
    )
    await _setup(hass, mock_config_entry)

    number = hass.states.get("number.philips_tv_name_100")
    assert number
    assert number.state == "70.0"

    select = hass.states.get("select.philips_tv_name_101")
    assert select
    assert select.state == "On"
    assert select.attributes["options"] == ["Off", "On"]

    switch = hass.states.get("switch.philips_tv_name_102")
    assert switch
    assert switch.state == STATE_OFF

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: number.entity_id, ATTR_VALUE: 20},
        blocking=True,
    )
    mock_tv.postMenuItemsSettingsUpdateData.assert_awaited_with(
        {SLIDER_ID: {"value": 20}}
    )

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: select.entity_id, ATTR_OPTION: "Off"},
        blocking=True,
    )
    mock_tv.postMenuItemsSettingsUpdateData.assert_awaited_with(
        {LIST_ID: {"select_item": 0}}
    )


async def test_no_nodes_selected(
    hass: HomeAssistant, mock_tv: PhilipsTV, mock_config_entry: MockConfigEntry
) -> None:
    """Test nothing is requested from the TV when no node is selected."""
    await _setup(hass, mock_config_entry)

    mock_tv.getMenuItemsSettingsCurrentValue.assert_not_called()
    assert hass.states.get("number.philips_tv_name_100") is None


async def test_toggle_multi_slider_and_parent(
    hass: HomeAssistant, mock_tv: PhilipsTV, mock_config_entry: MockConfigEntry
) -> None:
    """Test the toggle, multiple slider and parent node entities."""
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={CONF_MENU_NODES: _selected([TOGGLE_ID, MULTI_ID, PARENT_ID])},
    )
    await _setup(hass, mock_config_entry)

    assert hass.states.get("number.philips_tv_name_103_red").state == "4.0"
    parent = hass.states.get("select.philips_tv_name_104")
    assert parent.state == "string.on"
    assert parent.attributes["node_id"] == PARENT_ID
    assert parent.attributes["controllable"] is True

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.philips_tv_name_102"},
        blocking=True,
    )
    mock_tv.postMenuItemsSettingsUpdateData.assert_awaited_with(
        {TOGGLE_ID: {"value": True}}
    )

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.philips_tv_name_103_red", ATTR_VALUE: 7},
        blocking=True,
    )
    mock_tv.postMenuItemsSettingsUpdateData.assert_awaited_with(
        {MULTI_ID: {"value": 7, "slider_id": "red"}}
    )

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.philips_tv_name_104", ATTR_OPTION: "string.off"},
        blocking=True,
    )
    mock_tv.postMenuItemsSettingsUpdateData.assert_awaited_with(
        {PARENT_ID: {"activenode_id": 200}}
    )


async def test_invalid_option(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test selecting an option the TV does not offer."""
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_MENU_NODES: _selected([LIST_ID])}
    )
    await _setup(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: "select.philips_tv_name_101", ATTR_OPTION: "Dim"},
            blocking=True,
        )


@pytest.mark.parametrize(
    "error", [ConnectionFailure, GeneralFailure, KeyError("values")]
)
async def test_values_failure_marks_entities_unavailable(
    hass: HomeAssistant,
    mock_tv: PhilipsTV,
    mock_config_entry: MockConfigEntry,
    error: Exception,
) -> None:
    """Test a failing menu request does not break the other entities."""
    mock_tv.getMenuItemsSettingsCurrentValue.side_effect = error
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_MENU_NODES: _selected([SLIDER_ID])}
    )
    await _setup(hass, mock_config_entry)

    assert hass.states.get("number.philips_tv_name_100").state == STATE_UNAVAILABLE
    assert hass.states.get("media_player.philips_tv").state != STATE_UNAVAILABLE


async def test_values_not_fetched_in_standby(
    hass: HomeAssistant, mock_tv: PhilipsTV, mock_config_entry: MockConfigEntry
) -> None:
    """Test the menu values are not requested while the TV is in standby."""
    mock_tv.powerstate = "Standby"
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_MENU_NODES: _selected([SLIDER_ID])}
    )
    await _setup(hass, mock_config_entry)

    mock_tv.getMenuItemsSettingsCurrentValue.assert_not_called()
