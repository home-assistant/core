"""Test the Immich Frames config flow."""

from unittest.mock import patch
from uuid import UUID

from aiohttp import ClientError
from aioimmich.exceptions import ImmichError, ImmichUnauthorizedError
import pytest

from homeassistant.components.immich_frames.config_flow import (
    ImmichFramesConfigFlow,
    ImmichFramesOptionsFlow,
    _async_validate_source,
)
from homeassistant.components.immich_frames.const import (
    CONF_ALBUM_IDS,
    CONF_FRAME_NAME,
    CONF_IMMICH_ENTRY_ID,
    CONF_MODE,
    CONF_ORIENTATION,
    CONF_PAIR_WINDOW,
    CONF_PHOTO_FIT,
    CONF_SCREEN_SHAPE,
    CONF_SMART_QUERY,
    CONF_SOURCE,
    DEFAULT_SOURCE,
    DOMAIN,
    MODE_PAIRS,
    MODE_PAIRS_ONLY,
    ORIENTATION_LANDSCAPE,
    ORIENTATION_PORTRAIT,
    PHOTO_FIT_CROP,
    SOURCE_ALBUM,
    SOURCE_SMART,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import InvalidData

from tests.common import MockConfigEntry


def _options_input(source: str) -> dict[str, object]:
    """Return valid common options for source-specific flow tests."""
    return {
        CONF_SOURCE: source,
        CONF_MODE: "single",
        CONF_ORIENTATION: "any",
        "time_range": "all_time",
        CONF_PAIR_WINDOW: 2,
        CONF_SCREEN_SHAPE: "landscape",
        CONF_PHOTO_FIT: "show_full",
    }


async def test_source_validation_maps_parent_and_api_errors(
    parent_immich_entry: MockConfigEntry,
) -> None:
    """Source preflight maps missing, auth, transport, and API failures."""
    api = parent_immich_entry.runtime_data.api
    data = {CONF_SOURCE: DEFAULT_SOURCE}

    assert await _async_validate_source(None, data) == "immich_not_ready"

    api.search.async_get_all.side_effect = ImmichUnauthorizedError(
        {"message": "bad", "correlationId": "test"}
    )
    assert await _async_validate_source(api, data) == "immich_auth"

    api.search.async_get_all.side_effect = ClientError("offline")
    assert await _async_validate_source(api, data) == "assets_unavailable"

    api.search.async_get_all.side_effect = ImmichError(
        {"message": "server", "correlationId": "test"}
    )
    assert await _async_validate_source(api, data) == "assets_unavailable"


async def test_config_flow_handles_unavailable_parent_and_album(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Direct source steps preserve clear errors for unavailable selections."""
    flow = ImmichFramesConfigFlow()
    flow.hass = hass
    result = await flow.async_step_user(
        {CONF_IMMICH_ENTRY_ID: "missing", CONF_SOURCE: DEFAULT_SOURCE}
    )
    assert result["errors"]["base"] == "immich_unavailable"

    flow._data = {
        CONF_IMMICH_ENTRY_ID: "missing",
        CONF_SOURCE: SOURCE_ALBUM,
    }
    result = await flow.async_step_album()
    assert result["type"] == "abort"
    assert result["reason"] == "immich_not_ready"

    flow._data[CONF_IMMICH_ENTRY_ID] = parent_immich_entry.entry_id
    result = await flow.async_step_album({CONF_ALBUM_IDS: ["missing"]})
    assert result["type"] == "form"
    assert result["errors"]["base"] == "album_unavailable"


async def test_user_requires_immich(hass: HomeAssistant) -> None:
    """Test that a parent Immich entry is required."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "abort"
    assert result["reason"] == "immich_required"


async def test_user_creates_frame(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Test creating a frame linked to a loaded Immich entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
        },
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "Immich Frames"
    assert result["data"][CONF_IMMICH_ENTRY_ID] == parent_immich_entry.entry_id
    assert result["options"][CONF_SOURCE] == DEFAULT_SOURCE


async def test_user_aborts_when_frame_is_already_configured(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """A duplicate frame unique ID is rejected by the config flow."""
    frame_id = "0123456789abcdef0123456789abcdef"
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{parent_immich_entry.entry_id}|{frame_id}",
        data={CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    with patch(
        "homeassistant.components.immich_frames.config_flow.uuid4",
        return_value=UUID(frame_id),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
                CONF_SOURCE: DEFAULT_SOURCE,
            },
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_user_validation_errors(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Test invalid account validation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IMMICH_ENTRY_ID: "missing",
                CONF_SOURCE: DEFAULT_SOURCE,
            },
        )


async def test_user_aborts_when_immich_is_not_loaded(hass: HomeAssistant) -> None:
    """Test that an unavailable parent entry is not offered."""
    MockConfigEntry(domain="immich", state=ConfigEntryState.SETUP_ERROR).add_to_hass(
        hass
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "abort"
    assert result["reason"] == "immich_not_ready"


async def test_user_creates_album_frame(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Test the album source flow and selected album persistence."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_SOURCE: SOURCE_ALBUM,
        },
    )
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ALBUM_IDS: ["721e1a4b-aa12-441e-8d3b-5ac7ab283bb6"]}
    )

    assert result["type"] == "create_entry"
    assert result["options"][CONF_ALBUM_IDS]


async def test_album_flow_validates_empty_and_unknown_albums(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Album flows must reject empty and stale selections."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_SOURCE: SOURCE_ALBUM,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ALBUM_IDS: []}
    )
    assert result["errors"]["base"] == "album_required"

    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ALBUM_IDS: ["missing"]}
        )


async def test_album_flow_aborts_when_no_albums(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """A library with no albums should stop setup clearly."""
    parent_immich_entry.runtime_data.api.albums.async_get_all_albums.return_value = []
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_SOURCE: SOURCE_ALBUM,
        },
    )
    assert result["reason"] == "no_albums"


async def test_album_flow_reports_auth_and_connection_errors(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Album loading errors are shown without losing the flow."""
    api = parent_immich_entry.runtime_data.api
    for side_effect, expected_error in (
        (
            ImmichUnauthorizedError({"message": "bad", "correlationId": "test"}),
            "immich_auth",
        ),
        (ClientError("offline"), "albums_unavailable"),
        (
            ImmichError({"message": "server", "correlationId": "test"}),
            "albums_unavailable",
        ),
    ):
        api.albums.async_get_all_albums.side_effect = side_effect
        flow = ImmichFramesConfigFlow()
        flow.hass = hass
        flow._data = {
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_SOURCE: SOURCE_ALBUM,
        }
        result = await flow.async_step_album({CONF_ALBUM_IDS: ["album-1"]})
        assert result["errors"]["base"] == expected_error
    api.albums.async_get_all_albums.side_effect = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_SOURCE: SOURCE_ALBUM,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ALBUM_IDS: ["721e1a4b-aa12-441e-8d3b-5ac7ab283bb6"]},
    )
    assert result["type"] == "create_entry"


async def test_user_source_preflight_reports_unavailable_assets(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Source access is checked before a frame entry is created."""
    api = parent_immich_entry.runtime_data.api
    api.search.async_get_all.side_effect = ClientError("offline")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_SOURCE: DEFAULT_SOURCE,
        },
    )
    assert result["errors"]["base"] == "assets_unavailable"
    api.search.async_get_all.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_SOURCE: DEFAULT_SOURCE,
        },
    )
    assert result["type"] == "create_entry"


@pytest.mark.parametrize(
    "error",
    [
        ImmichUnauthorizedError({"message": "bad", "correlationId": "test"}),
        ClientError("offline"),
        ImmichError({"message": "server", "correlationId": "test"}),
    ],
    ids=("auth", "connection", "upstream"),
)
async def test_user_source_preflight_recovers_from_all_errors(
    hass: HomeAssistant,
    parent_immich_entry: MockConfigEntry,
    error: Exception,
) -> None:
    """Every user source preflight error can recover on retry."""
    api = parent_immich_entry.runtime_data.api
    api.search.async_get_all.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_SOURCE: DEFAULT_SOURCE,
        },
    )
    assert result["errors"]["base"] in {"assets_unavailable", "immich_auth"}
    api.search.async_get_all.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_SOURCE: DEFAULT_SOURCE,
        },
    )
    assert result["type"] == "create_entry"


async def test_album_source_preflight_reports_unavailable_assets(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Album access is checked after the selected albums are validated."""
    api = parent_immich_entry.runtime_data.api
    api.search.async_get_all_by_album_ids.side_effect = ClientError("offline")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_SOURCE: SOURCE_ALBUM,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ALBUM_IDS: ["721e1a4b-aa12-441e-8d3b-5ac7ab283bb6"]}
    )
    assert result["errors"]["base"] == "assets_unavailable"
    api.search.async_get_all_by_album_ids.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ALBUM_IDS: ["721e1a4b-aa12-441e-8d3b-5ac7ab283bb6"]},
    )
    assert result["type"] == "create_entry"


@pytest.mark.parametrize(
    "error",
    [
        ImmichUnauthorizedError({"message": "bad", "correlationId": "test"}),
        ClientError("offline"),
        ImmichError({"message": "server", "correlationId": "test"}),
    ],
    ids=("auth", "connection", "upstream"),
)
async def test_options_source_preflight_recovers_from_all_errors(
    hass: HomeAssistant,
    parent_immich_entry: MockConfigEntry,
    error: Exception,
) -> None:
    """Every options source preflight error can recover on retry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Recoverable options",
        data={
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_SOURCE: DEFAULT_SOURCE,
        },
    )
    entry.add_to_hass(hass)
    api = parent_immich_entry.runtime_data.api
    api.search.async_get_all.side_effect = error
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], _options_input(DEFAULT_SOURCE)
    )
    assert result["errors"]["base"] in {"assets_unavailable", "immich_auth"}
    api.search.async_get_all.side_effect = None
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], _options_input(DEFAULT_SOURCE)
    )
    assert result["type"] == "create_entry"


async def test_smart_source_preflight_reports_immich_errors(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Smart-source errors are shown before a frame entry is created."""
    api = parent_immich_entry.runtime_data.api
    api.search.async_smart_search.side_effect = ImmichError(
        {"message": "server", "correlationId": "test"}
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_SOURCE: SOURCE_SMART,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SMART_QUERY: "beach sunset"}
    )
    assert result["errors"]["base"] == "assets_unavailable"
    api.search.async_smart_search.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SMART_QUERY: "beach sunset"}
    )
    assert result["type"] == "create_entry"


async def test_user_creates_smart_frame(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Test the smart-search source flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_SOURCE: SOURCE_SMART,
        },
    )
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SMART_QUERY: "beach sunset"}
    )

    assert result["type"] == "create_entry"
    assert result["options"][CONF_SMART_QUERY] == "beach sunset"


async def test_smart_flow_requires_a_query(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Smart search should reject whitespace-only queries."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_SOURCE: SOURCE_SMART,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SMART_QUERY: "  "}
    )
    assert result["errors"][CONF_SMART_QUERY] == "smart_query_required"


async def test_options_flow_updates_display_settings(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Test options are stored separately from the entry identity."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living room",
        data={
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_FRAME_NAME: "Living room",
            CONF_SOURCE: DEFAULT_SOURCE,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_SOURCE: DEFAULT_SOURCE,
            CONF_MODE: MODE_PAIRS,
            CONF_ORIENTATION: ORIENTATION_PORTRAIT,
            "time_range": "1_month",
            CONF_PAIR_WINDOW: 3,
            CONF_SCREEN_SHAPE: "portrait",
            CONF_PHOTO_FIT: PHOTO_FIT_CROP,
        },
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_MODE] == MODE_PAIRS


async def test_options_flow_preflights_all_source(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Options do not save when the all-photos source cannot be reached."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Unavailable options",
        data={
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_FRAME_NAME: "Unavailable options",
            CONF_SOURCE: DEFAULT_SOURCE,
        },
    )
    entry.add_to_hass(hass)
    parent_immich_entry.runtime_data.api.search.async_get_all.side_effect = ClientError(
        "offline"
    )
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], _options_input(DEFAULT_SOURCE)
    )
    assert result["errors"]["base"] == "assets_unavailable"
    parent_immich_entry.runtime_data.api.search.async_get_all.side_effect = None
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], _options_input(DEFAULT_SOURCE)
    )
    assert result["type"] == "create_entry"


async def test_options_flow_configures_album_source(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Options flow should preserve source-specific album settings."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Album options",
        data={
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_FRAME_NAME: "Album options",
            CONF_SOURCE: DEFAULT_SOURCE,
        },
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_SOURCE: SOURCE_ALBUM,
            CONF_MODE: "single",
            CONF_ORIENTATION: "any",
            "time_range": "all_time",
            CONF_PAIR_WINDOW: 2,
            CONF_SCREEN_SHAPE: "landscape",
            CONF_PHOTO_FIT: "show_full",
        },
    )
    assert result["type"] == "form"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_ALBUM_IDS: ["721e1a4b-aa12-441e-8d3b-5ac7ab283bb6"]}
    )
    assert result["type"] == "create_entry"
    assert result["data"][CONF_ALBUM_IDS]


async def test_options_album_flow_validates_selection_and_source(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Options reject stale albums and unreachable album assets."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Album source validation",
        data={
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_FRAME_NAME: "Album source validation",
            CONF_SOURCE: DEFAULT_SOURCE,
        },
    )
    entry.add_to_hass(hass)
    flow = ImmichFramesOptionsFlow(entry)
    flow.hass = hass
    flow._data.update(_options_input(SOURCE_ALBUM))

    result = await flow.async_step_album({CONF_ALBUM_IDS: ["missing"]})
    assert result["errors"]["base"] == "album_unavailable"

    parent_immich_entry.runtime_data.api.search.async_get_all_by_album_ids.side_effect = ClientError(
        "offline"
    )
    result = await flow.async_step_album(
        {CONF_ALBUM_IDS: ["721e1a4b-aa12-441e-8d3b-5ac7ab283bb6"]}
    )
    assert result["errors"]["base"] == "assets_unavailable"
    parent_immich_entry.runtime_data.api.search.async_get_all_by_album_ids.side_effect = None
    result = await flow.async_step_album(
        {CONF_ALBUM_IDS: ["721e1a4b-aa12-441e-8d3b-5ac7ab283bb6"]}
    )
    assert result["type"] == "create_entry"


async def test_options_flow_validates_empty_and_missing_parent_albums(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Options reject empty album selections and unavailable parents."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Album validation",
        data={
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_FRAME_NAME: "Album validation",
            CONF_SOURCE: DEFAULT_SOURCE,
        },
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], _options_input(SOURCE_ALBUM)
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_ALBUM_IDS: []}
    )
    assert result["errors"]["base"] == "album_required"

    missing_parent = MockConfigEntry(
        domain=DOMAIN,
        title="Missing parent",
        data={
            CONF_IMMICH_ENTRY_ID: "missing",
            CONF_FRAME_NAME: "Missing parent",
            CONF_SOURCE: DEFAULT_SOURCE,
        },
    )
    missing_parent.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(missing_parent.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], _options_input(SOURCE_ALBUM)
    )
    assert result["type"] == "abort"
    assert result["reason"] == "immich_not_ready"


async def test_options_flow_rejects_pairs_only_landscape(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Pairs-only mode requires an orientation that can be paired."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Pair validation",
        data={
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_FRAME_NAME: "Pair validation",
            CONF_SOURCE: DEFAULT_SOURCE,
        },
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    values = _options_input(DEFAULT_SOURCE)
    values[CONF_MODE] = MODE_PAIRS_ONLY
    values[CONF_ORIENTATION] = ORIENTATION_LANDSCAPE
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], values
    )
    assert result["errors"][CONF_ORIENTATION] == "pairs_only_portrait_required"


async def test_options_album_flow_reports_immich_errors(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Options album loading maps upstream failures to a translated error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Album error",
        data={
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_FRAME_NAME: "Album error",
            CONF_SOURCE: DEFAULT_SOURCE,
        },
    )
    entry.add_to_hass(hass)
    get_albums = parent_immich_entry.runtime_data.api.albums.async_get_all_albums
    flow = ImmichFramesOptionsFlow(entry)
    flow.hass = hass
    flow._data.update(_options_input(SOURCE_ALBUM))
    for side_effect in (
        ImmichUnauthorizedError({"message": "bad", "correlationId": "test"}),
        ClientError("offline"),
        ImmichError({"message": "server", "correlationId": "test"}),
    ):
        get_albums.side_effect = side_effect
        result = await flow.async_step_album({CONF_ALBUM_IDS: ["album-1"]})
        assert result["errors"]["base"] in {"immich_auth", "albums_unavailable"}

    get_albums.side_effect = None
    get_albums.return_value = []
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], _options_input(SOURCE_ALBUM)
    )
    assert result["reason"] == "no_albums"


async def test_options_flow_configures_smart_source(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Options flow should preserve the smart-search query."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Smart options",
        data={
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_FRAME_NAME: "Smart options",
            CONF_SOURCE: DEFAULT_SOURCE,
        },
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_SOURCE: SOURCE_SMART,
            CONF_MODE: "single",
            CONF_ORIENTATION: "any",
            "time_range": "all_time",
            CONF_PAIR_WINDOW: 2,
            CONF_SCREEN_SHAPE: "landscape",
            CONF_PHOTO_FIT: "show_full",
        },
    )
    assert result["type"] == "form"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SMART_QUERY: "mountains"}
    )
    assert result["type"] == "create_entry"
    assert result["data"][CONF_SMART_QUERY] == "mountains"


async def test_options_smart_source_preflight_reports_unavailable_assets(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Options validate Smart Search before saving the query."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Unavailable smart options",
        data={
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_FRAME_NAME: "Unavailable smart options",
            CONF_SOURCE: DEFAULT_SOURCE,
        },
    )
    entry.add_to_hass(hass)
    parent_immich_entry.runtime_data.api.search.async_smart_search.side_effect = (
        ClientError("offline")
    )
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], _options_input(SOURCE_SMART)
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SMART_QUERY: "mountains"}
    )
    assert result["errors"]["base"] == "assets_unavailable"
    parent_immich_entry.runtime_data.api.search.async_smart_search.side_effect = None
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SMART_QUERY: "mountains"}
    )
    assert result["type"] == "create_entry"


async def test_options_flow_requires_smart_query(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Options reject a whitespace-only Smart Search query."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Smart validation",
        data={
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_FRAME_NAME: "Smart validation",
            CONF_SOURCE: DEFAULT_SOURCE,
        },
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], _options_input(SOURCE_SMART)
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SMART_QUERY: "  "}
    )
    assert result["errors"][CONF_SMART_QUERY] == "smart_query_required"


async def test_reconfigure_flow_keeps_generated_frame_name(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Test the explicit frame reconfiguration flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living room",
        data={
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_FRAME_NAME: "Living room",
            CONF_SOURCE: DEFAULT_SOURCE,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": entry.entry_id},
    )
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SOURCE: DEFAULT_SOURCE},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_all_source_preflight_reports_unavailable_assets(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Reconfiguration validates all-photos access before saving."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Unavailable reconfigure",
        data={
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_FRAME_NAME: "Unavailable reconfigure",
            CONF_SOURCE: DEFAULT_SOURCE,
        },
    )
    entry.add_to_hass(hass)
    parent_immich_entry.runtime_data.api.search.async_get_all.side_effect = ClientError(
        "offline"
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": entry.entry_id},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SOURCE: DEFAULT_SOURCE}
    )
    assert result["errors"]["base"] == "assets_unavailable"
    parent_immich_entry.runtime_data.api.search.async_get_all.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SOURCE: DEFAULT_SOURCE}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.parametrize(
    "error",
    [
        ImmichUnauthorizedError({"message": "bad", "correlationId": "test"}),
        ClientError("offline"),
        ImmichError({"message": "server", "correlationId": "test"}),
    ],
    ids=("auth", "connection", "upstream"),
)
async def test_reconfigure_source_preflight_recovers_from_all_errors(
    hass: HomeAssistant,
    parent_immich_entry: MockConfigEntry,
    error: Exception,
) -> None:
    """Every reconfigure source preflight error can recover on retry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Recoverable reconfigure",
        data={
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_SOURCE: DEFAULT_SOURCE,
        },
    )
    entry.add_to_hass(hass)
    api = parent_immich_entry.runtime_data.api
    api.search.async_get_all.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": entry.entry_id},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SOURCE: DEFAULT_SOURCE}
    )
    assert result["errors"]["base"] in {"assets_unavailable", "immich_auth"}
    api.search.async_get_all.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SOURCE: DEFAULT_SOURCE}
    )
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_flow_handles_album_and_smart_sources(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Reconfiguration exercises each source-specific branch and recovery."""
    api = parent_immich_entry.runtime_data.api
    for source, source_input in (
        (SOURCE_ALBUM, {CONF_ALBUM_IDS: ["721e1a4b-aa12-441e-8d3b-5ac7ab283bb6"]}),
        (SOURCE_SMART, {CONF_SMART_QUERY: "mountains"}),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            title=f"Reconfigure {source}",
            data={
                CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
                CONF_FRAME_NAME: f"Reconfigure {source}",
                CONF_SOURCE: DEFAULT_SOURCE,
            },
            options={
                CONF_SOURCE: DEFAULT_SOURCE,
                CONF_MODE: MODE_PAIRS,
                CONF_ORIENTATION: ORIENTATION_PORTRAIT,
                "time_range": "1_month",
                CONF_PAIR_WINDOW: 3,
                CONF_SCREEN_SHAPE: "portrait",
                CONF_PHOTO_FIT: PHOTO_FIT_CROP,
            },
        )
        entry.add_to_hass(hass)
        if source == SOURCE_ALBUM:
            api.search.async_get_all_by_album_ids.side_effect = ClientError("offline")
        else:
            api.search.async_smart_search.side_effect = ImmichError(
                {"message": "server", "correlationId": "test"}
            )
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reconfigure", "entry_id": entry.entry_id},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SOURCE: source},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], source_input
        )
        assert result["errors"]["base"] == "assets_unavailable"
        if source == SOURCE_ALBUM:
            api.search.async_get_all_by_album_ids.side_effect = None
        else:
            api.search.async_smart_search.side_effect = None
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], source_input
        )
        assert result["reason"] == "reconfigure_successful"
        await hass.async_block_till_done()
        assert entry.options[CONF_SOURCE] == source
        assert entry.options[CONF_MODE] == MODE_PAIRS
        assert entry.options[CONF_ORIENTATION] == ORIENTATION_PORTRAIT
        assert entry.options["time_range"] == "1_month"
        assert entry.options[CONF_PAIR_WINDOW] == 3
        assert entry.options[CONF_SCREEN_SHAPE] == "portrait"
        assert entry.options[CONF_PHOTO_FIT] == PHOTO_FIT_CROP
