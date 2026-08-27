"""Test the Collection Image config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.collection_image.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import MOCK_MEDIA_URI_1, MOCK_MEDIA_URI_BROWSE_ERROR, MOCK_MEDIA_URI_EMPTY

from tests.common import AsyncMock


@pytest.fixture
def mock_setup_entry():
    """Mock collection_image setup successfully."""

    with patch(
        "homeassistant.components.collection_image.async_setup_entry",
        new=AsyncMock(return_value=True),
    ) as mock_setup:
        yield mock_setup


async def _assert_successful_configure(
    hass: HomeAssistant,
    previous_step: config_entries.ConfigFlowResult,
    mock_setup_entry,
) -> None:

    result = await hass.config_entries.flow.async_configure(
        previous_step["flow_id"],
        {
            "media": [
                {
                    "media_content_id": MOCK_MEDIA_URI_1,
                    "media_content_type": "",
                }
            ],
        },
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "My pictures collection"
    assert result.get("data") == {
        "media": [
            {
                "media_content_id": MOCK_MEDIA_URI_1,
                "media_content_type": "",
            }
        ],
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_flow(
    hass: HomeAssistant, mock_media_source, mock_setup_entry
) -> None:
    """Test the config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {}

    await _assert_successful_configure(hass, result, mock_setup_entry)


async def test_config_flow_with_empty_dir(
    hass: HomeAssistant, mock_media_source, mock_setup_entry
) -> None:
    """Test the config flow with an empty directory."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "media": [
                {
                    "media_content_id": MOCK_MEDIA_URI_EMPTY,
                    "media_content_type": "",
                }
            ],
        },
    )
    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.FORM
    assert result.get("title") is None
    assert result.get("data") is None
    assert result.get("errors") == {"media": "selected_media_no_images"}
    assert len(mock_setup_entry.mock_calls) == 0

    # Try again successfully to ensure we can recover from errors
    await _assert_successful_configure(hass, result, mock_setup_entry)


async def test_config_flow_with_exception(
    hass: HomeAssistant, mock_media_source, mock_setup_entry
) -> None:
    """Test the config flow with a browse failure."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "media": [
                {
                    "media_content_id": MOCK_MEDIA_URI_BROWSE_ERROR,
                    "media_content_type": "",
                }
            ],
        },
    )
    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.FORM
    assert result.get("title") is None
    assert result.get("data") is None
    assert result.get("errors") == {"media": "failed_browse"}
    assert result.get("description_placeholders") == {
        "error": "Mock directory failed to browse"
    }
    assert len(mock_setup_entry.mock_calls) == 0

    await _assert_successful_configure(hass, result, mock_setup_entry)
