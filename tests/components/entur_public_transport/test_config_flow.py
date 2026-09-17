"""Tests for the Entur config flow."""

from typing import Any
from unittest.mock import patch

from homeassistant.components.entur_public_transport.api import (
    EnturApiError,
    EnturStopPlace,
)
from homeassistant.components.entur_public_transport.const import (
    CONF_EXPAND_PLATFORMS,
    CONF_NUMBER_OF_DEPARTURES,
    CONF_OMIT_NON_BOARDING,
    CONF_QUERY,
    CONF_SHOW_ON_MAP,
    CONF_STOP_ID,
    CONF_STOP_IDS,
    CONF_WHITELIST_LINES,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test configuring Entur from the UI."""
    place = EnturStopPlace(
        stop_id="NSR:StopPlace:548",
        name="Bergen busstasjon",
        display_name="Bergen busstasjon, Bergen",
        locality="Bergen",
        transport_modes=("bus", "rail"),
        role="parent",
    )

    with patch(
        "homeassistant.components.entur_public_transport.config_flow.async_search_stop_places",
        return_value=(place,),
    ) as search:
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
        CONF_STOP_IDS: ["NSR:StopPlace:548"],
        CONF_EXPAND_PLATFORMS: True,
        CONF_SHOW_ON_MAP: False,
        CONF_WHITELIST_LINES: [],
        CONF_OMIT_NON_BOARDING: True,
        CONF_NUMBER_OF_DEPARTURES: 2,
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

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_STOP_ID: "NSR:StopPlace:999"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_selection"}


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
