"""Test the Collection Image config flow."""

from freezegun import freeze_time
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant import config_entries
from homeassistant.components.collection_image.config_flow import IMAGE_MEDIA_URI
from homeassistant.components.collection_image.const import CONF_MEDIA, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import slugify

from .const import (
    MOCK_MEDIA_DIR_URI_1,
    MOCK_MEDIA_DIR_URI_2,
    MOCK_MEDIA_DIR_URI_BROWSE_ERROR,
    MOCK_MEDIA_DIR_URI_EMPTY,
)
from .helpers import data_from_uri

from tests.common import MockConfigEntry

TEST_TIME = "2026-09-12T07:12:00+00:00"
TEST_TIME_NEXT = "2026-09-12T07:30:00+00:00"


@pytest.mark.parametrize(
    ("uris", "expected_title"),
    [
        ([MOCK_MEDIA_DIR_URI_1], "My pictures collection"),
        ([MOCK_MEDIA_DIR_URI_1, MOCK_MEDIA_DIR_URI_2], "My pictures collection"),
        ([MOCK_MEDIA_DIR_URI_2, MOCK_MEDIA_DIR_URI_1], "Three pictures collection"),
    ],
)
@pytest.mark.usefixtures("mock_media_source")
@freeze_time(TEST_TIME)
async def test_config_flow(
    hass: HomeAssistant, uris: list[str], expected_title: str
) -> None:
    """Test the config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {}

    data = data_from_uri(uris)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], data)

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == expected_title
    assert result.get("data") == data

    await hass.async_block_till_done()

    state = hass.states.get(f"image.{slugify(expected_title)}")
    assert state and state.state == TEST_TIME


@pytest.mark.parametrize(
    ("uris", "error", "placeholders"),
    [
        (
            [MOCK_MEDIA_DIR_URI_EMPTY],
            "selected_media_no_images",
            {},
        ),
        (
            [MOCK_MEDIA_DIR_URI_EMPTY, MOCK_MEDIA_DIR_URI_EMPTY],
            "selected_media_no_images",
            {},
        ),
        (
            [MOCK_MEDIA_DIR_URI_BROWSE_ERROR],
            "failed_browse",
            {"error": "Mock directory failed to browse"},
        ),
        (
            [
                MOCK_MEDIA_DIR_URI_1,
                MOCK_MEDIA_DIR_URI_EMPTY,
                MOCK_MEDIA_DIR_URI_BROWSE_ERROR,
            ],
            "failed_browse",
            {"error": "Mock directory failed to browse"},
        ),
        (
            [MOCK_MEDIA_DIR_URI_1, IMAGE_MEDIA_URI],
            "invalid_selection",
            {"error": IMAGE_MEDIA_URI},
        ),
    ],
)
@freeze_time(TEST_TIME)
@pytest.mark.usefixtures("mock_media_source")
async def test_config_flow_error(
    hass: HomeAssistant,
    uris: list[str],
    error: str,
    placeholders: dict,
) -> None:
    """Test the config flow with an invalid media."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {}

    data = data_from_uri(uris)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.FORM
    assert result.get("title") is None
    assert result.get("data") is None

    media_key = next(
        key
        for key in result["data_schema"].schema
        if getattr(key, "schema", key) == CONF_MEDIA
    )
    for idx, uri in enumerate(uris):
        assert media_key.description["suggested_value"][idx]["media_content_id"] == uri
        assert (
            media_key.description["suggested_value"][idx]["metadata"]
            == data[CONF_MEDIA][idx]["metadata"]
        )

    assert result.get("errors") == {CONF_MEDIA: error}
    assert result.get("description_placeholders") == placeholders

    # Try again successfully to ensure we can recover from errors
    data = data_from_uri([MOCK_MEDIA_DIR_URI_1])
    expected_title = "My pictures collection"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], data)

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == expected_title
    assert result.get("data") == data

    await hass.async_block_till_done()

    state = hass.states.get(f"image.{slugify(expected_title)}")
    assert state and state.state == TEST_TIME


@pytest.mark.parametrize(
    ("entry_data", "expected_uri"),
    [
        pytest.param(
            data_from_uri([MOCK_MEDIA_DIR_URI_1]),
            MOCK_MEDIA_DIR_URI_1,
            id="legacy-data-array",
        ),
        pytest.param(
            data_from_uri(MOCK_MEDIA_DIR_URI_1),
            MOCK_MEDIA_DIR_URI_1,
            id="legacy-data-scalar",
        ),
    ],
)
@pytest.mark.usefixtures("mock_media_source")
async def test_reconfigure_flow(
    hass: HomeAssistant,
    entry_data: dict,
    expected_uri: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test reconfigure flow loads the original data and can update media."""
    freezer.move_to(TEST_TIME)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test collection",
        data=entry_data,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("image.test_collection")
    assert state and state.state == TEST_TIME

    freezer.move_to(TEST_TIME_NEXT)
    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    media_key = next(
        key
        for key in result["data_schema"].schema
        if getattr(key, "schema", key) == CONF_MEDIA
    )
    assert (
        media_key.description["suggested_value"][0]["media_content_id"] == expected_uri
    )

    # First try new data with error
    new_data = data_from_uri([MOCK_MEDIA_DIR_URI_EMPTY])

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        new_data,
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("data") is None
    assert result.get("errors") == {CONF_MEDIA: "selected_media_no_images"}

    # Now update again with a valid option, to recover
    new_data = data_from_uri([MOCK_MEDIA_DIR_URI_2])

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        new_data,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated_entry is not None
    assert updated_entry.data == new_data

    await hass.async_block_till_done()

    state = hass.states.get("image.test_collection")
    assert state and state.state == TEST_TIME_NEXT
