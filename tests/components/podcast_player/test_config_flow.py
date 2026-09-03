"""Tests for the Podcast Player config flow."""

from dataclasses import replace
from unittest.mock import AsyncMock

from aiopodcast import (
    FeedTooLargeError,
    InvalidFeedError,
    Podcast,
    PodcastConnectionError,
    PodcastHTTPError,
)
import pytest

from homeassistant.components.podcast_player.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_CANONICAL_URL, TEST_URL

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test the initial form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_create_entry(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test creating a podcast feed entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_URL: f"{TEST_URL}#episodes"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Example Podcast"
    assert result["data"] == {CONF_URL: TEST_URL}
    assert result["result"].unique_id == TEST_CANONICAL_URL
    mock_client.async_fetch.assert_awaited_once_with(TEST_URL)
    mock_setup_entry.assert_awaited_once()


async def test_duplicate_feed(
    hass: HomeAssistant,
    mock_client: AsyncMock,
) -> None:
    """Test rejecting an already configured feed URL before fetching it."""
    MockConfigEntry(
        domain=DOMAIN,
        title="Example Podcast",
        data={CONF_URL: TEST_URL},
        unique_id="https://old.example.com/feed.xml",
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_URL: TEST_URL},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_client.async_fetch.assert_not_awaited()


async def test_duplicate_canonical_feed(
    hass: HomeAssistant,
    mock_client: AsyncMock,
) -> None:
    """Test rejecting another URL that resolves to a configured feed."""
    MockConfigEntry(
        domain=DOMAIN,
        title="Example Podcast",
        data={CONF_URL: "https://example.com/alternate.xml"},
        unique_id=TEST_CANONICAL_URL,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_URL: TEST_URL},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_client.async_fetch.assert_awaited_once_with(TEST_URL)


@pytest.mark.parametrize(
    "url",
    [
        "not-a-url",
        "ftp://example.com/feed.xml",
        "https://user:password@example.com/feed.xml",
        "https://[invalid",
    ],
)
async def test_invalid_url(hass: HomeAssistant, url: str) -> None:
    """Test rejecting invalid podcast feed URLs."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_URL: url},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_URL: "invalid_url"}


async def test_invalid_canonical_url(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    podcast: Podcast,
) -> None:
    """Test rejecting a feed with an invalid canonical URL."""
    mock_client.async_fetch.return_value = replace(podcast, canonical_url="not-a-url")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_URL: TEST_URL},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_feed"}


@pytest.mark.parametrize(
    ("error", "flow_error"),
    [
        (PodcastConnectionError("Connection failed"), "cannot_connect"),
        (PodcastHTTPError(503), "cannot_connect"),
        (InvalidFeedError("Invalid feed"), "invalid_feed"),
        (FeedTooLargeError(1024), "invalid_feed"),
        (RuntimeError("Unexpected failure"), "unknown"),
    ],
)
async def test_validation_errors(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    error: Exception,
    flow_error: str,
) -> None:
    """Test errors while validating a podcast feed."""
    mock_client.async_fetch.side_effect = error

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_URL: TEST_URL},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": flow_error}
