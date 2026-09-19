"""Test the Immich Frames config flow."""

from aiohttp import ClientError
from aioimmich.exceptions import ImmichUnauthorizedError
import pytest

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
            CONF_FRAME_NAME: "Living room",
        },
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "Living room"
    assert result["data"][CONF_IMMICH_ENTRY_ID] == parent_immich_entry.entry_id
    assert result["data"][CONF_FRAME_NAME] == "Living room"
    assert result["data"][CONF_SOURCE] == DEFAULT_SOURCE


async def test_user_validation_errors(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Test invalid account and blank-name validation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IMMICH_ENTRY_ID: "missing",
                CONF_FRAME_NAME: "Living room",
                CONF_SOURCE: DEFAULT_SOURCE,
            },
        )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_FRAME_NAME: "   ",
            CONF_SOURCE: DEFAULT_SOURCE,
        },
    )
    assert result["errors"][CONF_FRAME_NAME] == "name_required"


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
            CONF_FRAME_NAME: "Album frame",
            CONF_SOURCE: SOURCE_ALBUM,
        },
    )
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ALBUM_IDS: ["721e1a4b-aa12-441e-8d3b-5ac7ab283bb6"]}
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_ALBUM_IDS]


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
            CONF_FRAME_NAME: "Album validation",
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
            CONF_FRAME_NAME: "No albums",
            CONF_SOURCE: SOURCE_ALBUM,
        },
    )
    assert result["reason"] == "no_albums"


async def test_album_flow_reports_auth_and_connection_errors(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Album loading errors are shown without losing the flow."""
    api = parent_immich_entry.runtime_data.api
    api.albums.async_get_all_albums.side_effect = ImmichUnauthorizedError(
        {"message": "bad", "correlationId": "test"}
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_FRAME_NAME: "Auth album",
            CONF_SOURCE: SOURCE_ALBUM,
        },
    )
    assert result["errors"]["base"] == "immich_auth"

    api.albums.async_get_all_albums.side_effect = ClientError("offline")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_FRAME_NAME: "Offline album",
            CONF_SOURCE: SOURCE_ALBUM,
        },
    )
    assert result["errors"]["base"] == "albums_unavailable"


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
            CONF_FRAME_NAME: "Keyword frame",
            CONF_SOURCE: SOURCE_SMART,
        },
    )
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SMART_QUERY: "beach sunset"}
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_SMART_QUERY] == "beach sunset"


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
            CONF_FRAME_NAME: "Empty query",
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


async def test_reconfigure_flow_updates_frame_name(
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
        {CONF_FRAME_NAME: "Kitchen", CONF_SOURCE: DEFAULT_SOURCE},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_flow_handles_album_and_smart_sources(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Reconfiguration exercises each source-specific branch."""
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
        )
        entry.add_to_hass(hass)
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reconfigure", "entry_id": entry.entry_id},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_FRAME_NAME: entry.title, CONF_SOURCE: source},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], source_input
        )
        assert result["reason"] == "reconfigure_successful"
        await hass.async_block_till_done()
