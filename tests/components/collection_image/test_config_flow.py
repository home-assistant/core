"""Test the Collection Image config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.collection_image.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import (
    MOCK_MEDIA_DIR_URI_1,
    MOCK_MEDIA_DIR_URI_BROWSE_ERROR,
    MOCK_MEDIA_DIR_URI_EMPTY,
)


@pytest.fixture
def mock_setup_entry():
    """Mock collection_image setup successfully."""

    with patch(
        "homeassistant.components.collection_image.async_setup_entry",
        new=AsyncMock(return_value=True),
    ) as mock_setup:
        yield mock_setup


def _data_from_uri(uri: str) -> dict:
    return {
        "media": {
            "media_content_id": uri,
            "media_content_type": "",
            "metadata": {"a": "b"},
        }
    }


@pytest.mark.usefixtures("mock_media_source")
async def test_config_flow(hass: HomeAssistant, mock_setup_entry) -> None:
    """Test the config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {}

    data = _data_from_uri(MOCK_MEDIA_DIR_URI_1)
    expected_title = "My pictures collection"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], data)

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == expected_title
    assert result.get("data") == data
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("uri", "error", "placeholders"),
    [
        (
            MOCK_MEDIA_DIR_URI_EMPTY,
            "selected_media_no_images",
            {},
        ),
        (
            MOCK_MEDIA_DIR_URI_BROWSE_ERROR,
            "failed_browse",
            {"error": "Mock directory failed to browse"},
        ),
    ],
)
@pytest.mark.usefixtures("mock_media_source")
async def test_config_flow_error(
    hass: HomeAssistant,
    mock_setup_entry,
    uri: str,
    error: str,
    placeholders: dict,
) -> None:
    """Test the config flow with an invalid media."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {}

    data = _data_from_uri(uri)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.FORM
    assert result.get("title") is None
    assert result.get("data") is None

    media_key = next(
        key
        for key in result["data_schema"].schema
        if getattr(key, "schema", key) == "media"
    )
    assert media_key.description["suggested_value"]["media_content_id"] == uri
    assert (
        media_key.description["suggested_value"]["metadata"]
        == data["media"]["metadata"]
    )

    assert result.get("errors") == {"media": error}
    assert result.get("description_placeholders") == placeholders
    assert len(mock_setup_entry.mock_calls) == 0

    # Try again successfully to ensure we can recover from errors
    data = _data_from_uri(MOCK_MEDIA_DIR_URI_1)
    expected_title = "My pictures collection"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], data)

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == expected_title
    assert result.get("data") == data
    assert len(mock_setup_entry.mock_calls) == 1
