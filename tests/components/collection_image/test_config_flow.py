"""Test the Collection Image config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.collection_image.const import DOMAIN
from homeassistant.components.media_player import BrowseMedia, MediaClass
from homeassistant.components.media_source import BrowseMediaSource
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def _assert_successful_configure(
    hass: HomeAssistant, previous_step: config_entries.ConfigFlowResult
):
    with (
        patch(
            "homeassistant.components.collection_image.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.collection_image.config_flow.async_browse_media",
            return_value=BrowseMediaSource(
                domain=None,
                identifier=None,
                media_class="",
                media_content_type="",
                title="",
                can_play=False,
                can_expand=True,
                children=[
                    BrowseMedia(
                        media_class=MediaClass.IMAGE,
                        media_content_id="media-source://mymedia/photo",
                        media_content_type="image/png",
                        title="a picture",
                        can_play=True,
                        can_expand=False,
                    ),
                ],
            ),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            previous_step["flow_id"],
            {
                "name": "Random Photo",
                "media": {
                    "media_content_id": "media-source://mymedia",
                    "media_content_type": "",
                },
            },
        )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "Random Photo"
    assert result.get("data") == {
        "name": "Random Photo",
        "media": {
            "media_content_id": "media-source://mymedia",
            "media_content_type": "",
        },
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_flow(hass: HomeAssistant) -> None:
    """Test the config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {}

    await _assert_successful_configure(hass, result)


async def test_config_flow_with_error(hass: HomeAssistant) -> None:
    """Test the config flow with an invalid directory."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {}

    with (
        patch(
            "homeassistant.components.collection_image.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.collection_image.config_flow.async_browse_media",
            return_value=BrowseMediaSource(
                domain=None,
                identifier=None,
                media_class="",
                media_content_type="",
                title="",
                can_play=False,
                can_expand=True,
                children=[],
            ),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "Random Photo",
                "media": {
                    "media_content_id": "media-source://mymedia_empty",
                    "media_content_type": "",
                },
            },
        )
        await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.FORM
    assert result.get("title") is None
    assert result.get("data") is None
    assert result.get("errors") == {"media": "selected_media_no_images"}
    assert len(mock_setup_entry.mock_calls) == 0

    # Try again successfully to ensure we can recover from errors
    await _assert_successful_configure(hass, result)


async def test_config_flow_with_exception(hass: HomeAssistant) -> None:
    """Test the config flow with a browse failure."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {}

    with (
        patch(
            "homeassistant.components.collection_image.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "Random Photo",
                "media": {
                    "media_content_id": "media-source://mymedia",
                    "media_content_type": "",
                },
            },
        )
        await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.FORM
    assert result.get("title") is None
    assert result.get("data") is None
    assert result.get("errors") == {"media": "failed_browse"}
    assert result.get("description_placeholders") == {
        "error": "Media Source not loaded"
    }
    assert len(mock_setup_entry.mock_calls) == 0

    await _assert_successful_configure(hass, result)
