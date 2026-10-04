"""Test the MobilityData config flow."""

import asyncio
from unittest.mock import MagicMock, patch

from aiomobilitydatabase import (
    DataType,
    GtfsFeed,
    GtfsRtFeed,
    Metadata,
    MobilityDatabaseAuthenticationError,
    MobilityDatabaseConnectionError,
    MobilityDatabaseNotFoundError,
    SearchResults,
    SourceInfo,
)
from aiomobilitydatabase.feeds import (
    StaticBuildProgress,
    StaticDataUnavailableError,
    StationGroup,
    Stop,
    StopLocationType,
)
import pytest

from homeassistant.components.mobilitydata.const import (
    CONF_FEED_ID,
    CONF_HEADSIGNS,
    CONF_REFRESH_TOKEN,
    CONF_ROUTE_IDS,
    CONF_SEARCH_QUERY,
    CONF_STOP_IDS,
    CONF_STOP_NAME,
    DOMAIN,
    SUBENTRY_TYPE_STOP,
)
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_LOCATION, CONF_STOP, CONF_ZONE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    EVENT_DATA_ENTRY_FLOW_PROGRESS_UPDATE,
    FlowResultType,
)

from .conftest import (
    DATASET,
    FEED_ID,
    RT_FEED,
    RT_FEED_ID,
    SEARCH_ITEM,
    SUBENTRY_ID,
    setup_integration,
)

from tests.common import MockConfigEntry, async_capture_events


def _authed_rt_feed(authentication_info_url: str | None) -> GtfsRtFeed:
    return GtfsRtFeed(
        id=RT_FEED_ID,
        data_type=DataType.GTFS_RT,
        provider="LADOT",
        entity_types=RT_FEED.entity_types,
        feed_references=[FEED_ID],
        source_info=SourceInfo(
            authentication_type=2,
            authentication_info_url=authentication_info_url,
        ),
    )


async def _advance_to_search(hass: HomeAssistant) -> str:
    """Complete the token step and return the flow id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_REFRESH_TOKEN: "refresh-token"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "search"
    return result["flow_id"]


async def _search_and_get_options(hass: HomeAssistant, flow_id: str) -> None:
    """Run a search that returns the canned result."""
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_SEARCH_QUERY: "los angeles"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "search"
    assert result["errors"] == {}


async def test_full_flow(
    hass: HomeAssistant, mock_feeds_client: MagicMock, mock_handle: MagicMock
) -> None:
    """Test the happy path with a progress-reported build."""
    build_release = asyncio.Event()

    async def slow_build(*args: object, **kwargs: object) -> MagicMock:
        await build_release.wait()
        return mock_handle

    mock_feeds_client.get_transit_feed.side_effect = slow_build

    flow_id = await _advance_to_search(hass)
    await _search_and_get_options(hass, flow_id)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_FEED_ID: FEED_ID}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "build"

    build_release.set()
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(flow_id)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "LADOT"
    assert result["data"] == {
        CONF_REFRESH_TOKEN: "refresh-token",
        CONF_FEED_ID: FEED_ID,
    }
    assert result["result"].unique_id == FEED_ID
    mock_handle.close.assert_called_once()


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(
            MobilityDatabaseAuthenticationError("bad token"),
            "invalid_auth",
            id="invalid_auth",
        ),
        pytest.param(
            MobilityDatabaseConnectionError("timeout"),
            "cannot_connect",
            id="cannot_connect",
        ),
    ],
)
async def test_token_errors_recover(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test token validation errors re-show the form and recover."""
    mock_feeds_client.catalog.get_metadata.side_effect = [
        side_effect,
        Metadata(version="1.0.0"),
    ]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_REFRESH_TOKEN: "refresh-token"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_REFRESH_TOKEN: "refresh-token"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "search"


async def test_search_no_results_then_success(
    hass: HomeAssistant, mock_feeds_client: MagicMock
) -> None:
    """Test an empty search shows an error and can be retried."""
    mock_feeds_client.catalog.search_feeds.side_effect = [
        SearchResults(total=0, results=[]),
        SearchResults(total=1, results=[SEARCH_ITEM]),
    ]
    flow_id = await _advance_to_search(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_SEARCH_QUERY: "nowhere"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_results"}

    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_SEARCH_QUERY: "los angeles"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}


async def test_search_nothing_entered(
    hass: HomeAssistant, mock_feeds_client: MagicMock
) -> None:
    """Test submitting the search form empty shows an error."""
    flow_id = await _advance_to_search(hass)
    result = await hass.config_entries.flow.async_configure(flow_id, {})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "search_or_select"}


@pytest.mark.parametrize(
    ("info_url", "expected_url"),
    [
        pytest.param(
            "https://developer.example.com/signup",
            "https://developer.example.com/signup",
            id="provider_url",
        ),
        pytest.param(
            None,
            f"https://mobilitydatabase.org/feeds/{FEED_ID}",
            id="catalog_fallback",
        ),
    ],
)
async def test_api_key_flow(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    info_url: str | None,
    expected_url: str,
) -> None:
    """Test the conditional API key step for authenticated realtime feeds."""
    mock_feeds_client.catalog.get_gtfs_feed_gtfs_rt_feeds.return_value = [
        _authed_rt_feed(info_url)
    ]
    flow_id = await _advance_to_search(hass)
    await _search_and_get_options(hass, flow_id)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_FEED_ID: FEED_ID}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "api_key"
    assert result["description_placeholders"] == {
        "authentication_info_url": expected_url
    }

    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_API_KEY: "producer-key"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_API_KEY] == "producer-key"


async def test_duplicate_feed_aborts_and_token_reused(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the account token is reused and duplicate feeds abort."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    # The existing entry's token still works, so the token step is skipped.
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "search"
    flow_id = result["flow_id"]
    await _search_and_get_options(hass, flow_id)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_FEED_ID: FEED_ID}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_stale_existing_token_prompts_again(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the token step is shown when the existing entry's token is dead."""
    mock_config_entry.add_to_hass(hass)
    mock_feeds_client.catalog.get_metadata.side_effect = [
        MobilityDatabaseAuthenticationError("expired"),
        Metadata(version="1.0.0"),
    ]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_REFRESH_TOKEN: "fresh-token"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "search"


async def test_build_failure_aborts(
    hass: HomeAssistant, mock_feeds_client: MagicMock
) -> None:
    """Test a failed dataset build aborts the flow."""
    mock_feeds_client.get_transit_feed.side_effect = StaticDataUnavailableError(
        "no hosted dataset"
    )
    flow_id = await _advance_to_search(hass)
    await _search_and_get_options(hass, flow_id)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_FEED_ID: FEED_ID}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "build_failed"


async def test_reauth_token(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth prompts for a new token when the token is invalid."""
    mock_config_entry.add_to_hass(hass)
    mock_feeds_client.catalog.get_metadata.side_effect = [
        MobilityDatabaseAuthenticationError("expired"),
        Metadata(version="1.0.0"),
    ]
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_token"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_REFRESH_TOKEN: "new-token"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_REFRESH_TOKEN] == "new-token"


async def test_reauth_api_key(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth prompts for a new API key when the token is still valid."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_API_KEY: "old-key"},
    )
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_api_key"
    assert (
        result["description_placeholders"]["authentication_info_url"]
        == f"https://mobilitydatabase.org/feeds/{FEED_ID}"
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new-key"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new-key"


async def _start_stop_flow(hass: HomeAssistant, entry: MockConfigEntry) -> dict:
    """Start the stop subentry flow and return the first step."""
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_STOP), context={"source": SOURCE_USER}
    )


async def test_add_stop_via_zone(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_handle: MagicMock,
) -> None:
    """Test adding a stop found through a zone entity."""
    await setup_integration(hass, mock_config_entry)
    hass.states.async_set(
        "zone.downtown",
        "0",
        {"latitude": 34.05, "longitude": -118.25, "radius": 800},
    )
    result = await _start_stop_flow(hass, mock_config_entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_ZONE: "zone.downtown"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "stop"
    circle = mock_handle.stations_in.call_args[0][0]
    assert circle.latitude == 34.05
    assert circle.radius_m == 800

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP: "2nd & spring"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "routes"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_ROUTE_IDS: ["R1"]}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "headsigns"
    mock_handle.headsigns_serving.assert_awaited_with("S2", "R1")

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_HEADSIGNS: ["Downtown"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry = next(
        subentry
        for subentry in mock_config_entry.subentries.values()
        if subentry.unique_id == "2nd & spring"
    )
    assert subentry.data == {
        CONF_STOP_IDS: ["S2"],
        CONF_STOP_NAME: "2nd & Spring",
        CONF_ROUTE_IDS: ["R1"],
        CONF_HEADSIGNS: ["Downtown"],
    }
    assert subentry.title == "2nd & Spring"

    # Creating a subentry reloads the entry so its sensors appear immediately.
    await hass.async_block_till_done()
    assert hass.states.get("sensor.2nd_spring_next_departure") is not None


async def test_add_stop_via_location(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_handle: MagicMock,
) -> None:
    """Test adding a stop found through a manual map circle."""
    await setup_integration(hass, mock_config_entry)
    result = await _start_stop_flow(hass, mock_config_entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_LOCATION: {"latitude": 34.06, "longitude": -118.24, "radius": 500}},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "stop"
    circle = mock_handle.stations_in.call_args[0][0]
    assert circle.radius_m == 500


async def test_add_stop_choose_one_error(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test submitting neither a zone nor a map area shows an error."""
    await setup_integration(hass, mock_config_entry)
    result = await _start_stop_flow(hass, mock_config_entry)
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "choose_one"}


async def test_add_stop_zone_beats_default_map_area(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_handle: MagicMock,
) -> None:
    """Test a picked zone wins over the always-present map suggestion."""
    await setup_integration(hass, mock_config_entry)
    hass.states.async_set(
        "zone.downtown",
        "0",
        {"latitude": 34.05, "longitude": -118.25, "radius": 800},
    )
    result = await _start_stop_flow(hass, mock_config_entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_ZONE: "zone.downtown",
            CONF_LOCATION: {"latitude": 34.0, "longitude": -118.0, "radius": 100},
        },
    )
    assert result["step_id"] == "stop"
    assert mock_handle.stations_in.call_args[0][0].radius_m == 800


async def test_add_stop_zone_not_found(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a vanished zone entity shows an error."""
    await setup_integration(hass, mock_config_entry)
    result = await _start_stop_flow(hass, mock_config_entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_ZONE: "zone.gone"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "zone_not_found"}


async def test_add_stop_no_stops_in_zone(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_handle: MagicMock,
) -> None:
    """Test an empty search area shows an error."""
    await setup_integration(hass, mock_config_entry)
    mock_handle.stations_in.return_value = []
    result = await _start_stop_flow(hass, mock_config_entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_LOCATION: {"latitude": 0.0, "longitude": 0.0, "radius": 100}},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_stops_in_zone"}


async def test_add_stop_duplicate_aborts(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a stop can only be configured once per feed."""
    await setup_integration(hass, mock_config_entry)
    result = await _start_stop_flow(hass, mock_config_entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_LOCATION: {"latitude": 34.05, "longitude": -118.25, "radius": 800}},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP: "1st & grand"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_add_stop_not_ready(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the flow aborts while the static index is still being acquired."""
    mock_feeds_client.get_transit_feed.side_effect = MobilityDatabaseConnectionError(
        "offline"
    )
    await setup_integration(hass, mock_config_entry)
    result = await _start_stop_flow(hass, mock_config_entry)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_ready"


async def test_add_stop_without_routes_or_headsigns(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_handle: MagicMock,
) -> None:
    """Test the filter steps are skipped when the stop offers no choices."""
    await setup_integration(hass, mock_config_entry)
    mock_handle.routes_serving.return_value = []
    mock_handle.headsigns_serving.return_value = []
    result = await _start_stop_flow(hass, mock_config_entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_LOCATION: {"latitude": 34.05, "longitude": -118.25, "radius": 800}},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP: "2nd & spring"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry = next(
        subentry
        for subentry in mock_config_entry.subentries.values()
        if subentry.unique_id == "2nd & spring"
    )
    assert subentry.data[CONF_STOP_IDS] == ["S2"]
    assert subentry.data[CONF_ROUTE_IDS] == []
    assert subentry.data[CONF_HEADSIGNS] == []


async def test_reconfigure_stop_filters(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring an existing stop's filters."""
    await setup_integration(hass, mock_config_entry)
    result = await mock_config_entry.start_subentry_reconfigure_flow(hass, SUBENTRY_ID)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "routes"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_ROUTE_IDS: ["R2"]}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "headsigns"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_HEADSIGNS: ["Uptown"]}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    subentry = mock_config_entry.subentries[SUBENTRY_ID]
    assert subentry.data[CONF_STOP_IDS] == ["S1"]
    assert subentry.data[CONF_ROUTE_IDS] == ["R2"]
    assert subentry.data[CONF_HEADSIGNS] == ["Uptown"]


@pytest.mark.parametrize(
    ("attribute", "side_effect", "error"),
    [
        pytest.param(
            "get_gtfs_feed",
            MobilityDatabaseConnectionError("timeout"),
            "cannot_connect",
            id="resolve_cannot_connect",
        ),
        pytest.param(
            "get_gtfs_feed",
            MobilityDatabaseNotFoundError("gone"),
            "unknown",
            id="resolve_unknown",
        ),
        pytest.param(
            "search_feeds",
            MobilityDatabaseConnectionError("timeout"),
            "cannot_connect",
            id="search_cannot_connect",
        ),
    ],
)
async def test_search_step_errors(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    attribute: str,
    side_effect: Exception,
    error: str,
) -> None:
    """Test catalog errors while searching or resolving show an error."""
    flow_id = await _advance_to_search(hass)
    await _search_and_get_options(hass, flow_id)
    getattr(mock_feeds_client.catalog, attribute).side_effect = side_effect
    user_input = (
        {CONF_FEED_ID: FEED_ID}
        if attribute == "get_gtfs_feed"
        else {CONF_SEARCH_QUERY: "again"}
    )
    result = await hass.config_entries.flow.async_configure(flow_id, user_input)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


async def test_build_progress_updates(
    hass: HomeAssistant, mock_feeds_client: MagicMock, mock_handle: MagicMock
) -> None:
    """Test download and index progress reaches the frontend."""
    build_release = asyncio.Event()

    async def slow_build(
        feed_id: str, api_key: str | None, on_progress: object = None
    ) -> MagicMock:
        assert callable(on_progress)
        on_progress(
            StaticBuildProgress(phase="download", done_bytes=1, total_bytes=None)
        )
        on_progress(
            StaticBuildProgress(phase="download", done_bytes=50, total_bytes=100)
        )
        on_progress(StaticBuildProgress(phase="index", done_bytes=80, total_bytes=100))
        await build_release.wait()
        return mock_handle

    mock_feeds_client.get_transit_feed.side_effect = slow_build
    events = async_capture_events(hass, EVENT_DATA_ENTRY_FLOW_PROGRESS_UPDATE)

    flow_id = await _advance_to_search(hass)
    await _search_and_get_options(hass, flow_id)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_FEED_ID: FEED_ID}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    build_release.set()
    await hass.async_block_till_done()

    assert [event.data["progress"] for event in events] == [0.25, 0.9]
    result = await hass.config_entries.flow.async_configure(flow_id)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_reauth_cannot_connect_aborts(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth aborts when the catalog cannot be reached."""
    mock_config_entry.add_to_hass(hass)
    mock_feeds_client.catalog.get_metadata.side_effect = (
        MobilityDatabaseConnectionError("offline")
    )
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_reauth_token_errors_recover(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test bad replacement tokens re-show the reauth form until valid."""
    mock_config_entry.add_to_hass(hass)
    mock_feeds_client.catalog.get_metadata.side_effect = [
        MobilityDatabaseAuthenticationError("expired"),
        MobilityDatabaseAuthenticationError("still bad"),
        MobilityDatabaseConnectionError("offline"),
        Metadata(version="1.0.0"),
    ]
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_token"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_REFRESH_TOKEN: "bad-token"}
    )
    assert result["errors"] == {"base": "invalid_auth"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_REFRESH_TOKEN: "any-token"}
    )
    assert result["errors"] == {"base": "cannot_connect"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_REFRESH_TOKEN: "good-token"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_add_stop_entry_not_loaded(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the stop flow aborts when the entry is not set up."""
    mock_config_entry.add_to_hass(hass)
    result = await _start_stop_flow(hass, mock_config_entry)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_ready"


def _suggested_location(result: dict) -> dict | None:
    """Extract the map picker's suggested value from the form schema."""
    for key in result["data_schema"].schema:
        if str(key) == "location":
            return (key.description or {}).get("suggested_value")
    return None


async def test_add_stop_map_centered_on_coverage(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the map picker is pre-centered on the feed's stops."""
    await setup_integration(hass, mock_config_entry)
    result = await _start_stop_flow(hass, mock_config_entry)
    assert _suggested_location(result) == {
        "latitude": pytest.approx(34.055),
        "longitude": pytest.approx(-118.245),
        "radius": 1000,
    }


async def test_add_stop_without_coverage_center(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_handle: MagicMock,
) -> None:
    """Test the area picker still works when stops lack coordinates."""
    mock_handle.stops = [
        Stop(
            id="S9",
            name="No coords",
            latitude=None,
            longitude=None,
            parent_station=None,
            location_type=StopLocationType.STOP,
            stop_code=None,
            platform_code=None,
            wheelchair_boarding=None,
            description=None,
            url=None,
            zone_id=None,
            timezone=None,
        )
    ]
    await setup_integration(hass, mock_config_entry)
    result = await _start_stop_flow(hass, mock_config_entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert _suggested_location(result) is None


@pytest.mark.parametrize(
    ("step_input", "final_step"),
    [
        pytest.param(None, "routes", id="routes"),
        pytest.param({CONF_ROUTE_IDS: ["R1"]}, "headsigns", id="headsigns"),
    ],
)
async def test_add_stop_unloaded_mid_flow(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    step_input: dict | None,
    final_step: str,
) -> None:
    """Test filter steps abort if the entry unloads mid-flow."""
    await setup_integration(hass, mock_config_entry)
    result = await _start_stop_flow(hass, mock_config_entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_LOCATION: {"latitude": 34.05, "longitude": -118.25, "radius": 800}},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP: "2nd & spring"}
    )
    assert result["step_id"] == "routes"
    if step_input is not None:
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], step_input
        )
        assert result["step_id"] == final_step

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_ready"


async def test_title_includes_feed_name(
    hass: HomeAssistant, mock_feeds_client: MagicMock
) -> None:
    """Test entry titles stay distinct when a provider has multiple feeds."""
    mock_feeds_client.catalog.get_gtfs_feed.return_value = GtfsFeed(
        id=FEED_ID,
        data_type=DataType.GTFS,
        provider="WMATA",
        feed_name="Rail",
        latest_dataset=DATASET,
    )
    flow_id = await _advance_to_search(hass)
    await _search_and_get_options(hass, flow_id)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_FEED_ID: FEED_ID}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "WMATA Rail"


async def test_station_hierarchy_grouped(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_handle: MagicMock,
) -> None:
    """Test a multi-platform station is offered and stored as one stop."""
    mock_handle.stations_in.return_value = [
        StationGroup(id="2nd & spring", name="2nd & Spring", stop_ids=("S2",)),
        StationGroup(id="ST1", name="Metro Center", stop_ids=("P1", "P2")),
    ]
    await setup_integration(hass, mock_config_entry)
    result = await _start_stop_flow(hass, mock_config_entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_LOCATION: {"latitude": 34.05, "longitude": -118.25, "radius": 800}},
    )
    assert result["step_id"] == "stop"
    options = result["data_schema"].schema[CONF_STOP].config["options"]
    assert options == [
        {"value": "2nd & spring", "label": "2nd & Spring"},
        {"value": "ST1", "label": "Metro Center"},
    ]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP: "ST1"}
    )
    assert result["step_id"] == "routes"
    mock_handle.routes_serving.assert_any_await("P1")
    mock_handle.routes_serving.assert_any_await("P2")

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_ROUTE_IDS: []}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_HEADSIGNS: []}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry = next(
        subentry
        for subentry in mock_config_entry.subentries.values()
        if subentry.unique_id == "ST1"
    )
    assert subentry.data[CONF_STOP_IDS] == ["P1", "P2"]
    assert subentry.title == "Metro Center"


async def test_reauth_token_updates_sibling_entries(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a rotated token propagates to and reloads entries sharing it."""
    mock_config_entry.add_to_hass(hass)
    sibling = MockConfigEntry(
        domain=DOMAIN,
        title="WMATA Rail",
        unique_id="mdb-1847",
        data={CONF_REFRESH_TOKEN: "refresh-token", CONF_FEED_ID: "mdb-1847"},
    )
    sibling.add_to_hass(hass)
    other_account = MockConfigEntry(
        domain=DOMAIN,
        title="Other",
        unique_id="mdb-99",
        data={CONF_REFRESH_TOKEN: "different-token", CONF_FEED_ID: "mdb-99"},
    )
    other_account.add_to_hass(hass)
    # The sibling hit the same expired token and has its own reauth pending
    mock_feeds_client.catalog.get_metadata.side_effect = [
        MobilityDatabaseAuthenticationError("expired"),
        MobilityDatabaseAuthenticationError("expired"),
        Metadata(version="1.0.0"),
    ]
    sibling_result = await sibling.start_reauth_flow(hass)
    assert sibling_result["step_id"] == "reauth_token"

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_token"
    with patch(
        "homeassistant.components.mobilitydata.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_REFRESH_TOKEN: "new-token"}
        )
        assert result["reason"] == "reauth_successful"
        await hass.async_block_till_done()
    assert mock_config_entry.data[CONF_REFRESH_TOKEN] == "new-token"
    assert sibling.data[CONF_REFRESH_TOKEN] == "new-token"
    assert other_account.data[CONF_REFRESH_TOKEN] == "different-token"
    # The sibling was reloaded with the new token, aborting its reauth flow
    assert sibling.state is ConfigEntryState.LOADED
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)
