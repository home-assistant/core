"""Tests for the Entur config flow."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.entur_public_transport import (
    _async_migrate_subentry_display_data,
)
from homeassistant.components.entur_public_transport.api import (
    EnturApiError,
    EnturRoute,
    EnturStopPlace,
)
from homeassistant.components.entur_public_transport.const import (
    CONF_EXPAND_PLATFORMS,
    CONF_MANUAL_WHITELIST_LINES,
    CONF_NUMBER_OF_DEPARTURES,
    CONF_OMIT_NON_BOARDING,
    CONF_QUERY,
    CONF_SHOW_ON_MAP,
    CONF_STOP_ID,
    CONF_STOP_IDS,
    CONF_WHITELIST_LINES,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER, FlowType
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData

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
    assert subentry.title == "🚌 🚆 Bergen busstasjon · 1 · bus · RUT, 2 · SKY"
    assert subentry.data == {
        CONF_STOP_ID: place.stop_id,
        CONF_WHITELIST_LINES: [route.line_id, "SKY:Line:2"],
        "route_labels": {
            "RUT:Line:1": "1 · bus · RUT",
            "SKY:Line:2": "2 · SKY",
        },
        "stop_place_types": ["busStation", "railStation"],
        "stop_place_metadata_version": 1,
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
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, "stop-subentry")
        assert result["step_id"] == "reconfigure"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={CONF_QUERY: "Bergen"}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={CONF_STOP_ID: new_place.stop_id}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={
                CONF_WHITELIST_LINES: [new_route.line_id],
                CONF_MANUAL_WHITELIST_LINES: "",
            },
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.subentries["stop-subentry"].data == {
        CONF_STOP_ID: new_place.stop_id,
        CONF_WHITELIST_LINES: [new_route.line_id],
        "route_labels": {"RUT:Line:1": "1 · bus · RUT"},
        "stop_place_types": ["busStation"],
        "stop_place_metadata_version": 1,
    }
    assert (
        entry.subentries["stop-subentry"].title
        == "🚌 Bergen busstasjon · 1 · bus · RUT"
    )


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
                    CONF_WHITELIST_LINES: ["BRA:Line:101"],
                },
            }
        ],
    )
    entry.add_to_hass(hass)

    with patch(
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
    ):
        await _async_migrate_subentry_display_data(hass, entry)

    subentry = entry.subentries["stop-subentry"]
    assert subentry.title == "🚏 Hønefoss sentrum · 101 · BRA"
    assert subentry.data["route_labels"] == {"BRA:Line:101": "101 · BRA"}
    assert subentry.data["stop_place_types"] == ["onstreetBus"]
    assert subentry.data["stop_place_metadata_version"] == 1
