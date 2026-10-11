"""Tests for the Entur config flow."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.entur_public_transport import (
    _async_migrate_subentry_display_data,
)
from homeassistant.components.entur_public_transport.api import (
    EnturApiError,
    EnturQuay,
    EnturRoute,
    EnturStopPlace,
)
from homeassistant.components.entur_public_transport.config_flow import (
    EnturConfigFlow,
    EnturStopPlaceSubentryFlow,
    _async_reconcile_subentry_entities,
    _combine_line_whitelist,
    _configured_platform_summary,
    _configured_route_summary,
    _parse_line_whitelist,
    _place_description,
    _platform_schema,
    _platform_selection,
    _route_labels,
    _route_schema,
    _selection_option,
    _stop_is_configured,
    _stop_selector_schema,
)
from homeassistant.components.entur_public_transport.const import (
    CONF_EXPAND_PLATFORMS,
    CONF_MANUAL_WHITELIST_LINES,
    CONF_NUMBER_OF_DEPARTURES,
    CONF_OMIT_NON_BOARDING,
    CONF_PLATFORM_MODE,
    CONF_QUAY_IDS,
    CONF_QUERY,
    CONF_RECONFIGURE_ACTION,
    CONF_STOP_ID,
    CONF_STOP_IDS,
    CONF_STOP_PLACE_NAME,
    CONF_WHITELIST_LINES,
    DOMAIN,
    PLATFORM_MODE_ALL,
    PLATFORM_MODE_SELECTED,
    PLATFORM_MODE_STOP_PLACE,
    RECONFIGURE_ACTION_EDIT,
    RECONFIGURE_ACTION_REPLACE,
)
from homeassistant.config_entries import (
    SOURCE_IMPORT,
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    FlowType,
)
from homeassistant.const import CONF_NAME, CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers.entity_registry import EntityRegistry

from tests.common import MockConfigEntry


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test configuring Entur from the UI."""
    place = EnturStopPlace(
        stop_id="NSR:StopPlace:548",
        name="Bergen busstasjon",
        display_name="Bergen busstasjon, Bergen",
        locality="Bergen",
        transport_modes=("bus", "rail"),
        role="parent",
        stop_place_types=("busStation", "railStation"),
    )
    route = EnturRoute(
        line_id="RUT:Line:1",
        public_code="1",
        transport_mode="bus",
    )

    with (
        patch(
            "homeassistant.components.entur_public_transport.config_flow.async_search_stop_places",
            return_value=(place,),
        ) as search,
        patch(
            "homeassistant.components.entur_public_transport.config_flow.async_get_stop_routes",
            return_value=(route,),
        ) as get_routes,
        patch(
            "homeassistant.components.entur_public_transport.config_flow.async_get_stop_quays",
            return_value=(
                EnturQuay(
                    quay_id="NSR:Quay:1",
                    name="Bergen busstasjon",
                    public_code="A",
                ),
            ),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_QUERY: "Bergen"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "select_stop"
        search.assert_awaited_once_with(hass, "Bergen")

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_STOP_ID: place.stop_id}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "select_routes"
        get_routes.assert_awaited_once_with(hass, place.stop_id)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_WHITELIST_LINES: [route.line_id],
                CONF_MANUAL_WHITELIST_LINES: "SKY:Line:2",
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "select_platforms"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PLATFORM_MODE: PLATFORM_MODE_STOP_PLACE}
        )
        assert result["step_id"] == "confirm"
        assert result["description_placeholders"]["stop_id"] == place.stop_id
        assert (
            result["description_placeholders"]["entur_url"]
            == "https://entur.no/nearby-stop-place-detail?id=NSR%3AStopPlace%3A548"
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Entur"
    assert result["data"] == {
        CONF_NAME: "Entur",
        CONF_STOP_IDS: [],
        CONF_EXPAND_PLATFORMS: True,
        CONF_SHOW_ON_MAP: False,
        CONF_WHITELIST_LINES: [],
        CONF_OMIT_NON_BOARDING: True,
        CONF_NUMBER_OF_DEPARTURES: 2,
    }
    assert result["next_flow"][0] is FlowType.CONFIG_SUBENTRIES_FLOW

    subentry_result = await hass.config_entries.subentries.async_configure(
        result["next_flow"][1], user_input={}
    )
    assert subentry_result["type"] is FlowResultType.CREATE_ENTRY
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    subentry = next(iter(entry.subentries.values()))
    assert subentry.title == "🚌 🚆 Bergen busstasjon · 1 RUT (1-RUT), 2 SKY (2-SKY)"
    assert subentry.data == {
        CONF_STOP_ID: place.stop_id,
        CONF_STOP_PLACE_NAME: place.name,
        CONF_WHITELIST_LINES: [route.line_id, "SKY:Line:2"],
        CONF_PLATFORM_MODE: PLATFORM_MODE_STOP_PLACE,
        CONF_QUAY_IDS: [],
        CONF_SHOW_ON_MAP: False,
        "route_labels": {
            "RUT:Line:1": "1 RUT (1-RUT)",
            "SKY:Line:2": "2 SKY (2-SKY)",
        },
        "stop_place_types": ["busStation", "railStation"],
        "stop_place_metadata_version": 4,
    }


async def test_user_flow_rejects_short_query(hass: HomeAssistant) -> None:
    """Test that the UI rejects a search query that is too short."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_QUERY: "O"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "query_too_short"}


async def test_user_flow_accepts_manual_route_without_api_routes(
    hass: HomeAssistant,
) -> None:
    """Test adding a manual line ID when route discovery is empty."""
    place = EnturStopPlace(
        stop_id="NSR:StopPlace:548",
        name="Bergen busstasjon",
        display_name="Bergen busstasjon, Bergen",
        locality="Bergen",
        transport_modes=("bus",),
        role="parent",
        stop_place_types=("busStation",),
    )

    with (
        patch(
            "homeassistant.components.entur_public_transport.config_flow.async_search_stop_places",
            return_value=(place,),
        ),
        patch(
            "homeassistant.components.entur_public_transport.config_flow.async_get_stop_routes",
            return_value=(),
        ),
        patch(
            "homeassistant.components.entur_public_transport.config_flow.async_get_stop_quays",
            return_value=(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_QUERY: "Bergen"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_STOP_ID: place.stop_id}
        )
        assert result["step_id"] == "select_routes"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_MANUAL_WHITELIST_LINES: "SKY:Line:2"},
        )
        assert result["step_id"] == "select_platforms"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PLATFORM_MODE: PLATFORM_MODE_STOP_PLACE}
        )
        assert result["step_id"] == "confirm"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    subentry_result = await hass.config_entries.subentries.async_configure(
        result["next_flow"][1], user_input={}
    )
    assert subentry_result["type"] is FlowResultType.CREATE_ENTRY
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    subentry = next(iter(entry.subentries.values()))
    assert subentry.data[CONF_WHITELIST_LINES] == ["SKY:Line:2"]


async def test_user_flow_handles_no_results(hass: HomeAssistant) -> None:
    """Test that the UI explains when the search has no matches."""
    with patch(
        "homeassistant.components.entur_public_transport.config_flow.async_search_stop_places",
        return_value=(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_QUERY: "Not a real stop"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_results"}


async def test_subentry_flow_can_select_one_platform(hass: HomeAssistant) -> None:
    """Test adding exactly one platform from a stop place."""
    place = EnturStopPlace(
        stop_id="NSR:StopPlace:548",
        name="Bergen busstasjon",
        display_name="Bergen busstasjon, Bergen",
        locality="Bergen",
        transport_modes=("bus",),
        role="parent",
        stop_place_types=("busStation",),
    )
    quay = EnturQuay(
        quay_id="NSR:Quay:48550",
        name="Bergen busstasjon",
        public_code="A",
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: "Entur",
            CONF_STOP_IDS: [],
            CONF_EXPAND_PLATFORMS: True,
            CONF_SHOW_ON_MAP: False,
            CONF_WHITELIST_LINES: [],
            CONF_OMIT_NON_BOARDING: True,
            CONF_NUMBER_OF_DEPARTURES: 2,
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.entur_public_transport.config_flow.async_search_stop_places",
            return_value=(place,),
        ),
        patch(
            "homeassistant.components.entur_public_transport.config_flow.async_get_stop_routes",
            return_value=(),
        ),
        patch(
            "homeassistant.components.entur_public_transport.config_flow.async_get_stop_quays",
            return_value=(quay,),
        ),
    ):
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "stop_place"), context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={CONF_QUERY: "Bergen"}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={CONF_STOP_ID: place.stop_id}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={CONF_MANUAL_WHITELIST_LINES: ""}
        )
        assert result["step_id"] == "select_platforms"
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={
                CONF_PLATFORM_MODE: PLATFORM_MODE_SELECTED,
                CONF_QUAY_IDS: [quay.quay_id],
                CONF_SHOW_ON_MAP: True,
            },
        )
        assert result["step_id"] == "confirm"
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry = next(iter(entry.subentries.values()))
    assert subentry.data[CONF_PLATFORM_MODE] == PLATFORM_MODE_SELECTED
    assert subentry.data[CONF_QUAY_IDS] == [quay.quay_id]
    assert subentry.data[CONF_STOP_PLACE_NAME] == place.name
    assert subentry.data[CONF_SHOW_ON_MAP] is True


async def test_subentry_reconfigure_updates_stop_and_routes(
    hass: HomeAssistant,
) -> None:
    """Test changing a stop place and its per-stop route filter."""
    old_stop_id = "NSR:StopPlace:1"
    new_place = EnturStopPlace(
        stop_id="NSR:StopPlace:548",
        name="Bergen busstasjon",
        display_name="Bergen busstasjon, Bergen",
        locality="Bergen",
        transport_modes=("bus",),
        role="parent",
        stop_place_types=("busStation",),
    )
    new_route = EnturRoute(
        line_id="RUT:Line:1",
        public_code="1",
        transport_mode="bus",
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: "Entur",
            CONF_STOP_IDS: [],
            CONF_EXPAND_PLATFORMS: True,
            CONF_SHOW_ON_MAP: False,
            CONF_WHITELIST_LINES: [],
            CONF_OMIT_NON_BOARDING: True,
            CONF_NUMBER_OF_DEPARTURES: 2,
        },
        subentries_data=[
            {
                "subentry_id": "stop-subentry",
                "subentry_type": "stop_place",
                "title": "Old stop",
                "unique_id": old_stop_id,
                "data": {
                    CONF_STOP_ID: old_stop_id,
                    CONF_WHITELIST_LINES: ["RUT:Line:9"],
                },
            }
        ],
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.entur_public_transport.config_flow.async_search_stop_places",
            return_value=(new_place,),
        ),
        patch(
            "homeassistant.components.entur_public_transport.config_flow.async_get_stop_routes",
            return_value=(new_route,),
        ),
        patch(
            "homeassistant.components.entur_public_transport.config_flow.async_get_stop_quays",
            return_value=(),
        ),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, "stop-subentry")
        assert result["step_id"] == "reconfigure"
        assert result["description_placeholders"]["routes"] == "9 RUT (9-RUT)"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={CONF_RECONFIGURE_ACTION: RECONFIGURE_ACTION_REPLACE},
        )
        assert result["step_id"] == "replace_stop"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={CONF_QUERY: "Bergen"}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={CONF_STOP_ID: new_place.stop_id}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={
                CONF_MANUAL_WHITELIST_LINES: "",
            },
        )
        assert result["step_id"] == "select_platforms"
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={CONF_PLATFORM_MODE: PLATFORM_MODE_STOP_PLACE}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.subentries["stop-subentry"].data == {
        CONF_STOP_ID: new_place.stop_id,
        CONF_STOP_PLACE_NAME: new_place.name,
        CONF_WHITELIST_LINES: [],
        CONF_PLATFORM_MODE: PLATFORM_MODE_STOP_PLACE,
        CONF_QUAY_IDS: [],
        CONF_SHOW_ON_MAP: False,
        "route_labels": {},
        "stop_place_types": ["busStation"],
        "stop_place_metadata_version": 4,
    }
    assert (
        entry.subentries["stop-subentry"].title == "🚌 Bergen busstasjon · all routes"
    )


async def test_subentry_reconfigure_blocks_selected_platform_edit_on_api_error(
    hass: HomeAssistant,
) -> None:
    """Test platform selections are not discarded when quay lookup fails."""
    stop_id = "NSR:StopPlace:548"
    place = EnturStopPlace(
        stop_id=stop_id,
        name="Bergen busstasjon",
        display_name="Bergen busstasjon, Bergen",
        locality="Bergen",
        transport_modes=("bus",),
        role="parent",
        stop_place_types=("busStation",),
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        subentries_data=[
            {
                "subentry_id": "stop-subentry",
                "subentry_type": "stop_place",
                "title": place.name,
                "unique_id": stop_id,
                "data": {
                    CONF_STOP_ID: stop_id,
                    CONF_PLATFORM_MODE: PLATFORM_MODE_SELECTED,
                    CONF_QUAY_IDS: ["NSR:Quay:1"],
                },
            }
        ],
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.entur_public_transport.config_flow.async_get_stop_place",
            return_value=place,
        ),
        patch(
            "homeassistant.components.entur_public_transport.config_flow.async_get_stop_routes",
            return_value=(),
        ),
        patch(
            "homeassistant.components.entur_public_transport.config_flow.async_get_stop_quays",
            side_effect=EnturApiError,
        ),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, "stop-subentry")
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={CONF_RECONFIGURE_ACTION: RECONFIGURE_ACTION_EDIT},
        )

    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_subentry_reconfigure_edits_routes_on_current_stop(
    hass: HomeAssistant,
) -> None:
    """Test maintaining routes and map visibility without searching again."""
    place = EnturStopPlace(
        stop_id="NSR:StopPlace:548",
        name="Bergen busstasjon",
        display_name="Bergen busstasjon, Bergen",
        locality="Bergen",
        transport_modes=("bus",),
        role="parent",
        stop_place_types=("busStation",),
    )
    route = EnturRoute(
        line_id="RUT:Line:1",
        public_code="1",
        transport_mode="bus",
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: "Entur",
            CONF_STOP_IDS: [],
            CONF_EXPAND_PLATFORMS: True,
            CONF_SHOW_ON_MAP: False,
            CONF_WHITELIST_LINES: [],
            CONF_OMIT_NON_BOARDING: True,
            CONF_NUMBER_OF_DEPARTURES: 2,
        },
        subentries_data=[
            {
                "subentry_id": "stop-subentry",
                "subentry_type": "stop_place",
                "title": "Bergen busstasjon",
                "unique_id": place.stop_id,
                "data": {
                    CONF_STOP_ID: place.stop_id,
                    CONF_STOP_PLACE_NAME: place.name,
                    CONF_WHITELIST_LINES: [route.line_id],
                    "route_labels": {route.line_id: "1 RUT (1-RUT)"},
                    CONF_PLATFORM_MODE: PLATFORM_MODE_ALL,
                    CONF_QUAY_IDS: [],
                    CONF_SHOW_ON_MAP: True,
                },
            }
        ],
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.entur_public_transport.config_flow.async_get_stop_place",
            return_value=place,
        ),
        patch(
            "homeassistant.components.entur_public_transport.config_flow.async_get_stop_routes",
            return_value=(route,),
        ),
        patch(
            "homeassistant.components.entur_public_transport.config_flow.async_get_stop_quays",
            return_value=(),
        ),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, "stop-subentry")
        assert result["description_placeholders"] == {
            "name": place.name,
            "routes": "1 RUT (1-RUT)",
            "platforms": "∞",
            "show_on_map": "✓",
        }

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={CONF_RECONFIGURE_ACTION: RECONFIGURE_ACTION_EDIT},
        )
        assert result["step_id"] == "select_routes"
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={
                CONF_WHITELIST_LINES: [],
                CONF_MANUAL_WHITELIST_LINES: "",
            },
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={
                CONF_PLATFORM_MODE: PLATFORM_MODE_STOP_PLACE,
                CONF_SHOW_ON_MAP: False,
            },
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["reason"] == "reconfigure_successful"
    data = entry.subentries["stop-subentry"].data
    assert data[CONF_STOP_ID] == place.stop_id
    assert data[CONF_WHITELIST_LINES] == []
    assert data[CONF_PLATFORM_MODE] == PLATFORM_MODE_STOP_PLACE
    assert data[CONF_SHOW_ON_MAP] is False


async def test_reconfigure_removes_replaced_stop_entities(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
) -> None:
    """Test replacing a stop clears its entities from the registry."""
    old_stop_id = "NSR:StopPlace:1"
    new_stop_id = "NSR:StopPlace:2"
    entry = MockConfigEntry(
        domain=DOMAIN,
        subentries_data=[
            {
                "subentry_id": "stop-subentry",
                "subentry_type": "stop_place",
                "title": "Old stop",
                "unique_id": old_stop_id,
                "data": {CONF_STOP_ID: old_stop_id},
            }
        ],
    )
    entry.add_to_hass(hass)
    registry = entity_registry
    registry.async_get_or_create(
        "sensor",
        DOMAIN,
        old_stop_id,
        config_entry=entry,
        config_subentry_id="stop-subentry",
    )

    _async_reconcile_subentry_entities(
        hass,
        entry,
        entry.subentries["stop-subentry"],
        new_stop_id,
        PLATFORM_MODE_STOP_PLACE,
        [],
    )

    assert registry.async_get_entity_id("sensor", DOMAIN, old_stop_id) is None


async def test_reconfigure_removes_deselected_platform_entities(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
) -> None:
    """Test changing platform selection keeps only selected platform entities."""
    stop_id = "NSR:StopPlace:1"
    selected_quay_id = "NSR:Quay:1"
    removed_quay_id = "NSR:Quay:2"
    entry = MockConfigEntry(
        domain=DOMAIN,
        subentries_data=[
            {
                "subentry_id": "stop-subentry",
                "subentry_type": "stop_place",
                "title": "Stop",
                "unique_id": stop_id,
                "data": {CONF_STOP_ID: stop_id},
            }
        ],
    )
    entry.add_to_hass(hass)
    registry = entity_registry
    for unique_id in (stop_id, selected_quay_id, removed_quay_id):
        registry.async_get_or_create(
            "sensor",
            DOMAIN,
            unique_id,
            config_entry=entry,
            config_subentry_id="stop-subentry",
        )

    _async_reconcile_subentry_entities(
        hass,
        entry,
        entry.subentries["stop-subentry"],
        stop_id,
        PLATFORM_MODE_SELECTED,
        [selected_quay_id],
    )

    assert registry.async_get_entity_id("sensor", DOMAIN, stop_id) is None
    assert registry.async_get_entity_id("sensor", DOMAIN, selected_quay_id) is not None
    assert registry.async_get_entity_id("sensor", DOMAIN, removed_quay_id) is None


async def test_user_flow_handles_api_error(hass: HomeAssistant) -> None:
    """Test that the UI explains when Entur cannot be reached."""
    with patch(
        "homeassistant.components.entur_public_transport.config_flow.async_search_stop_places",
        side_effect=EnturApiError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_QUERY: "Bergen"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_rejects_invalid_selection(hass: HomeAssistant) -> None:
    """Test that the UI does not accept a stop outside the search results."""
    place = EnturStopPlace(
        stop_id="NSR:StopPlace:548",
        name="Bergen busstasjon",
        display_name="Bergen busstasjon, Bergen",
        locality="Bergen",
        transport_modes=("bus",),
        role="standalone",
        stop_place_types=("onstreetBus",),
    )

    with patch(
        "homeassistant.components.entur_public_transport.config_flow.async_search_stop_places",
        return_value=(place,),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_QUERY: "Bergen"}
        )

        with pytest.raises(InvalidData):
            await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={CONF_STOP_ID: "NSR:StopPlace:999"}
            )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_stop"


async def test_import_flow(hass: HomeAssistant) -> None:
    """Test importing an existing YAML platform configuration."""
    import_data: dict[str, Any] = {
        "platform": DOMAIN,
        CONF_NAME: "Transport",
        CONF_STOP_IDS: ["NSR:StopPlace:548"],
        CONF_EXPAND_PLATFORMS: False,
        CONF_SHOW_ON_MAP: True,
        CONF_WHITELIST_LINES: ["RUT:Line:1"],
        CONF_OMIT_NON_BOARDING: False,
        CONF_NUMBER_OF_DEPARTURES: 4,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=import_data,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Transport"
    assert result["data"] == {
        CONF_NAME: "Transport",
        CONF_STOP_IDS: ["NSR:StopPlace:548"],
        CONF_EXPAND_PLATFORMS: False,
        CONF_SHOW_ON_MAP: True,
        CONF_WHITELIST_LINES: ["RUT:Line:1"],
        CONF_OMIT_NON_BOARDING: False,
        CONF_NUMBER_OF_DEPARTURES: 4,
    }


async def test_migrate_legacy_subentry_display_data(hass: HomeAssistant) -> None:
    """Test that older subentries show their existing route filter."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: "Entur",
            CONF_STOP_IDS: [],
            CONF_EXPAND_PLATFORMS: True,
            CONF_SHOW_ON_MAP: False,
            CONF_WHITELIST_LINES: [],
            CONF_OMIT_NON_BOARDING: True,
            CONF_NUMBER_OF_DEPARTURES: 2,
        },
        subentries_data=[
            {
                "subentry_id": "stop-subentry",
                "subentry_type": "stop_place",
                "title": "Hønefoss sentrum",
                "unique_id": "NSR:StopPlace:1",
                "data": {
                    CONF_STOP_ID: "NSR:StopPlace:1",
                    CONF_WHITELIST_LINES: ["BRA:Line:4_6101"],
                },
            }
        ],
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.entur_public_transport.async_get_stop_place",
            return_value=EnturStopPlace(
                stop_id="NSR:StopPlace:1",
                name="Hønefoss sentrum",
                display_name="Hønefoss sentrum, Hønefoss",
                locality="Hønefoss",
                transport_modes=("bus",),
                role="standalone",
                stop_place_types=("onstreetBus",),
            ),
        ),
        patch(
            "homeassistant.components.entur_public_transport.async_get_stop_routes",
            return_value=(
                EnturRoute(
                    line_id="BRA:Line:4_6101",
                    public_code="4_6101",
                    name="101 Drammen-Vikersund/Hønefoss",
                    transport_mode="bus",
                ),
            ),
        ),
    ):
        await _async_migrate_subentry_display_data(hass, entry)

    subentry = entry.subentries["stop-subentry"]
    assert subentry.title == "🚏 Hønefoss sentrum · 101 BRA (4_6101-BRA)"
    assert subentry.data["route_labels"] == {"BRA:Line:4_6101": "101 BRA (4_6101-BRA)"}
    assert subentry.data["stop_place_types"] == ["onstreetBus"]
    assert subentry.data["stop_place_metadata_version"] == 4
    assert subentry.data[CONF_PLATFORM_MODE] == PLATFORM_MODE_ALL
    assert subentry.data[CONF_QUAY_IDS] == []
    assert subentry.data[CONF_STOP_PLACE_NAME] == "Hønefoss sentrum"
    assert subentry.data[CONF_SHOW_ON_MAP] is False


async def test_migrate_legacy_subentry_skips_unavailable_stop(
    hass: HomeAssistant,
) -> None:
    """Test unavailable metadata does not rewrite an existing subentry title."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        subentries_data=[
            {
                "subentry_id": "stop-subentry",
                "subentry_type": "stop_place",
                "title": "🚏 Existing stop · all routes",
                "unique_id": "NSR:StopPlace:1",
                "data": {CONF_STOP_ID: "NSR:StopPlace:1"},
            }
        ],
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.entur_public_transport.async_get_stop_place",
        side_effect=EnturApiError,
    ):
        await _async_migrate_subentry_display_data(hass, entry)

    subentry = entry.subentries["stop-subentry"]
    assert subentry.title == "🚏 Existing stop · all routes"
    assert subentry.data == {CONF_STOP_ID: "NSR:StopPlace:1"}


def test_combine_line_whitelist_parses_manual_multiline_ids() -> None:
    """Test manual line IDs are split, merged, and deduplicated."""
    assert _combine_line_whitelist(
        ["RUT:Line:1"],
        "SKY:Line:2" + chr(10) + "GOA:Line:3, RUT:Line:1",
    ) == ["RUT:Line:1", "SKY:Line:2", "GOA:Line:3"]


def test_config_flow_helpers_cover_selection_and_fallbacks() -> None:
    """Test the helper branches used to build Entur configuration forms."""
    route = EnturRoute(line_id="RUT:Line:1", public_code="1", transport_mode="bus")
    quay = EnturQuay(quay_id="NSR:Quay:1", name="Central station", public_code="A")
    place = EnturStopPlace(
        stop_id="NSR:StopPlace:1",
        name="Central station",
        display_name="Central station",
        locality="",
        transport_modes=(),
        role="parent",
        stop_place_types=(),
    )

    assert _parse_line_whitelist([" RUT:Line:1 ", "", "RUT:Line:1"]) == ["RUT:Line:1"]
    assert _parse_line_whitelist("RUT:Line:1, SKY:Line:2") == [
        "RUT:Line:1",
        "SKY:Line:2",
    ]
    assert _selection_option("id", "Label") == {"value": "id", "label": "Label"}
    assert _route_schema((), ["MANUAL:Line:1"])
    assert _route_schema((route,), [route.line_id, "MANUAL:Line:1"])
    assert _platform_schema((), PLATFORM_MODE_STOP_PLACE, [], False)
    assert _platform_schema(
        (quay,), PLATFORM_MODE_SELECTED, [quay.quay_id, "NSR:Quay:2"], True
    )
    assert _stop_selector_schema((place,))
    assert EnturConfigFlow.async_get_supported_subentry_types(MockConfigEntry())

    assert _platform_selection(
        {CONF_PLATFORM_MODE: "invalid", CONF_QUAY_IDS: [quay.quay_id]}, (quay,)
    ) == (PLATFORM_MODE_STOP_PLACE, [quay.quay_id])
    assert _platform_selection(
        {
            CONF_PLATFORM_MODE: PLATFORM_MODE_SELECTED,
            CONF_QUAY_IDS: [quay.quay_id, quay.quay_id, "NSR:Quay:2"],
        },
        (quay,),
    ) == (PLATFORM_MODE_SELECTED, [quay.quay_id])
    assert _configured_route_summary([], {}) == "—"
    assert _configured_route_summary(["MANUAL:Line:1"], {}) == "1 MANUAL (1-MANUAL)"
    assert _configured_platform_summary(PLATFORM_MODE_STOP_PLACE, []) == "●"
    assert _configured_platform_summary(PLATFORM_MODE_SELECTED, [quay.quay_id]) == "1"
    assert _configured_platform_summary(PLATFORM_MODE_ALL, []) == "∞"
    assert _route_labels(
        [route.line_id, "MANUAL:Line:1"], (route,), {"MANUAL:Line:1": "Manual"}
    ) == {route.line_id: "1 RUT (1-RUT)", "MANUAL:Line:1": "Manual"}
    assert _place_description(place) == {
        "name": "Central station",
        "display_name": "Central station",
        "locality": "—",
        "transport_modes": "—",
        "stop_id": "NSR:StopPlace:1",
        "entur_url": "https://entur.no/nearby-stop-place-detail?id=NSR%3AStopPlace%3A1",
    }

    entry = MockConfigEntry(
        data={CONF_STOP_IDS: ["NSR:StopPlace:legacy"]},
        subentries_data=[
            {
                "subentry_id": "stop-subentry",
                "subentry_type": "stop_place",
                "title": "Central station",
                "data": {CONF_STOP_ID: "NSR:StopPlace:1"},
            }
        ],
    )
    assert _stop_is_configured(entry, "NSR:StopPlace:legacy")
    assert _stop_is_configured(entry, "NSR:StopPlace:1")
    assert not _stop_is_configured(
        entry, "NSR:StopPlace:1", exclude_subentry_id="stop-subentry"
    )


async def test_config_flow_defensive_paths(hass: HomeAssistant) -> None:
    """Test API failures and invalid choices remain recoverable in the UI."""
    place = EnturStopPlace(
        stop_id="NSR:StopPlace:1",
        name="Central station",
        display_name="Central station",
        locality="City",
        transport_modes=("bus",),
        role="standalone",
    )

    flow = EnturConfigFlow()
    flow.hass = hass
    flow.handler = DOMAIN
    flow.context = {"source": SOURCE_USER}
    await flow.async_step_select_stop({CONF_STOP_ID: "NSR:StopPlace:missing"})
    flow._places = (place,)
    with (
        patch(
            "homeassistant.components.entur_public_transport.config_flow.async_get_stop_routes",
            side_effect=EnturApiError,
        ),
        patch(
            "homeassistant.components.entur_public_transport.config_flow.async_get_stop_quays",
            side_effect=EnturApiError,
        ),
    ):
        result = await flow.async_step_select_stop({CONF_STOP_ID: place.stop_id})
    assert result["step_id"] == "select_routes"

    empty_flow = EnturConfigFlow()
    empty_flow.hass = hass
    empty_flow.handler = DOMAIN
    empty_flow.context = {"source": SOURCE_USER}
    assert (await empty_flow.async_step_select_routes())["type"] is FlowResultType.ABORT
    assert (await empty_flow.async_step_select_platforms())[
        "type"
    ] is FlowResultType.ABORT
    assert (await empty_flow.async_step_confirm())["type"] is FlowResultType.ABORT

    flow._selected_place = place
    result = await flow.async_step_select_platforms(
        {CONF_PLATFORM_MODE: PLATFORM_MODE_SELECTED}
    )
    assert result["errors"] == {"base": "select_platform"}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_STOP_IDS: ["NSR:StopPlace:legacy"]},
        subentries_data=[
            {
                "subentry_id": "stop-subentry",
                "subentry_type": "stop_place",
                "title": "Central station",
                "data": {CONF_STOP_ID: place.stop_id},
            }
        ],
    )
    entry.add_to_hass(hass)

    duplicate_flow = EnturStopPlaceSubentryFlow()
    duplicate_flow.hass = hass
    duplicate_flow.handler = (entry.entry_id, "stop_place")
    duplicate_flow.context = {"source": SOURCE_USER}
    assert (await duplicate_flow.async_step_user({"place": place}))[
        "reason"
    ] == "already_configured"

    reconfigure_flow = EnturStopPlaceSubentryFlow()
    reconfigure_flow.hass = hass
    reconfigure_flow.handler = (entry.entry_id, "stop_place")
    reconfigure_flow.context = {
        "source": SOURCE_RECONFIGURE,
        "subentry_id": "stop-subentry",
    }
    with patch(
        "homeassistant.components.entur_public_transport.config_flow.async_get_stop_place",
        side_effect=EnturApiError,
    ):
        result = await reconfigure_flow.async_step_reconfigure(
            {CONF_RECONFIGURE_ACTION: RECONFIGURE_ACTION_EDIT}
        )
    assert result["errors"] == {"base": "cannot_connect"}

    empty_entry = MockConfigEntry(
        domain=DOMAIN,
        subentries_data=[
            {
                "subentry_id": "empty-subentry",
                "subentry_type": "stop_place",
                "title": "Empty stop",
                "data": {},
            }
        ],
    )
    empty_entry.add_to_hass(hass)
    empty_reconfigure_flow = EnturStopPlaceSubentryFlow()
    empty_reconfigure_flow.hass = hass
    empty_reconfigure_flow.handler = (empty_entry.entry_id, "stop_place")
    empty_reconfigure_flow.context = {
        "source": SOURCE_RECONFIGURE,
        "subentry_id": "empty-subentry",
    }
    assert (
        await empty_reconfigure_flow.async_step_reconfigure(
            {CONF_RECONFIGURE_ACTION: RECONFIGURE_ACTION_EDIT}
        )
    )["type"] is FlowResultType.ABORT

    reconfigure_flow = EnturStopPlaceSubentryFlow()
    reconfigure_flow.hass = hass
    reconfigure_flow.handler = (entry.entry_id, "stop_place")
    reconfigure_flow.context = {
        "source": SOURCE_RECONFIGURE,
        "subentry_id": "stop-subentry",
    }
    with (
        patch(
            "homeassistant.components.entur_public_transport.config_flow.async_get_stop_place",
            return_value=place,
        ),
        patch(
            "homeassistant.components.entur_public_transport.config_flow.async_get_stop_routes",
            side_effect=EnturApiError,
        ),
        patch(
            "homeassistant.components.entur_public_transport.config_flow.async_get_stop_quays",
            side_effect=EnturApiError,
        ),
    ):
        result = await reconfigure_flow.async_step_reconfigure(
            {CONF_RECONFIGURE_ACTION: RECONFIGURE_ACTION_EDIT}
        )
    assert result["step_id"] == "select_routes"

    search_flow = EnturStopPlaceSubentryFlow()
    search_flow.hass = hass
    assert (await search_flow._async_step_search("user", {CONF_QUERY: "O"}))[
        "errors"
    ] == {"base": "query_too_short"}
    with patch(
        "homeassistant.components.entur_public_transport.config_flow.async_search_stop_places",
        side_effect=EnturApiError,
    ):
        result = await search_flow._async_step_search("user", {CONF_QUERY: "Oslo"})
    assert result["errors"] == {"base": "cannot_connect"}
    with patch(
        "homeassistant.components.entur_public_transport.config_flow.async_search_stop_places",
        return_value=(),
    ):
        result = await search_flow._async_step_search("user", {CONF_QUERY: "Oslo"})
    assert result["errors"] == {"base": "no_results"}

    selection_flow = EnturStopPlaceSubentryFlow()
    selection_flow.hass = hass
    selection_flow._places = (place,)
    selection_flow._existing_stop_id = place.stop_id
    await selection_flow.async_step_select_stop({CONF_STOP_ID: "NSR:StopPlace:missing"})
    with (
        patch(
            "homeassistant.components.entur_public_transport.config_flow.async_get_stop_routes",
            side_effect=EnturApiError,
        ),
        patch(
            "homeassistant.components.entur_public_transport.config_flow.async_get_stop_quays",
            side_effect=EnturApiError,
        ),
    ):
        result = await selection_flow.async_step_select_stop(
            {CONF_STOP_ID: place.stop_id}
        )
    assert result["step_id"] == "select_routes"

    empty_subentry_flow = EnturStopPlaceSubentryFlow()
    empty_subentry_flow.hass = hass
    assert (await empty_subentry_flow.async_step_select_routes())[
        "type"
    ] is FlowResultType.ABORT
    assert (await empty_subentry_flow.async_step_select_platforms())[
        "type"
    ] is FlowResultType.ABORT
    assert (await empty_subentry_flow.async_step_confirm())[
        "type"
    ] is FlowResultType.ABORT

    selection_flow._selected_place = place
    result = await selection_flow.async_step_select_platforms(
        {CONF_PLATFORM_MODE: PLATFORM_MODE_SELECTED}
    )
    assert result["errors"] == {"base": "select_platform"}

    configured_flow = EnturStopPlaceSubentryFlow()
    configured_flow.hass = hass
    configured_flow.handler = (entry.entry_id, "stop_place")
    configured_flow.context = {
        "source": SOURCE_RECONFIGURE,
        "subentry_id": "stop-subentry",
    }
    configured_flow._selected_place = EnturStopPlace(
        stop_id="NSR:StopPlace:legacy",
        name="Legacy",
        display_name="Legacy",
        locality="City",
        transport_modes=(),
        role="standalone",
    )
    assert (await configured_flow.async_step_confirm({}))[
        "reason"
    ] == "already_configured"

    _async_reconcile_subentry_entities(
        hass,
        entry,
        entry.subentries["stop-subentry"],
        place.stop_id,
        PLATFORM_MODE_ALL,
        [],
    )
