"""The tests for the feedreader config flow."""

from unittest.mock import Mock, patch
import urllib

import pytest

from homeassistant.components.feedreader.const import (
    CONF_MAX_ENTRIES,
    DEFAULT_MAX_ENTRIES,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import create_mock_entry
from .const import FEED_TITLE, URL, VALID_CONFIG_DEFAULT


@pytest.fixture(name="feedparser")
def feedparser_fixture(feed_one_event: bytes) -> Mock:
    """Patch libraries."""
    with (
        patch(
            "homeassistant.components.feedreader.config_flow.feedparser.http.get",
            return_value=feed_one_event,
        ) as feedparser,
    ):
        yield feedparser


@pytest.fixture(name="setup_entry")
def setup_entry_fixture(feed_one_event: bytes) -> Mock:
    """Patch libraries."""
    with (
        patch("homeassistant.components.feedreader.async_setup_entry") as setup_entry,
    ):
        yield setup_entry


async def test_user(hass: HomeAssistant, feedparser, setup_entry) -> None:
    """Test starting a flow by user."""
    # init user flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # success
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_URL: URL}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == FEED_TITLE
    assert result["data"][CONF_URL] == URL
    assert result["options"][CONF_MAX_ENTRIES] == DEFAULT_MAX_ENTRIES


async def test_user_errors(
    hass: HomeAssistant, feedparser, setup_entry, feed_one_event
) -> None:
    """Test starting a flow by user which results in an URL error."""
    # init user flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # raise URLError
    feedparser.side_effect = urllib.error.URLError("Test")
    feedparser.return_value = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_URL: URL}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "url_error"}

    # success
    feedparser.side_effect = None
    feedparser.return_value = feed_one_event
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_URL: URL}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == FEED_TITLE
    assert result["data"][CONF_URL] == URL
    assert result["options"][CONF_MAX_ENTRIES] == DEFAULT_MAX_ENTRIES


async def test_reconfigure(hass: HomeAssistant, feedparser) -> None:
    """Test starting a reconfigure flow."""
    entry = create_mock_entry(VALID_CONFIG_DEFAULT)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # init user flow
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # success
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload"
    ) as mock_async_reload:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_URL: "http://other.rss.local/rss_feed.xml",
            },
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        CONF_URL: "http://other.rss.local/rss_feed.xml",
    }

    await hass.async_block_till_done()
    assert mock_async_reload.call_count == 1


async def test_reconfigure_errors(
    hass: HomeAssistant, feedparser, setup_entry, feed_one_event
) -> None:
    """Test starting a reconfigure flow by user which results in an URL error."""
    entry = create_mock_entry(VALID_CONFIG_DEFAULT)
    entry.add_to_hass(hass)

    # init user flow
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # raise URLError
    feedparser.side_effect = urllib.error.URLError("Test")
    feedparser.return_value = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_URL: "http://other.rss.local/rss_feed.xml",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "url_error"}

    # success
    feedparser.side_effect = None
    feedparser.return_value = feed_one_event

    # success
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_URL: "http://other.rss.local/rss_feed.xml",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        CONF_URL: "http://other.rss.local/rss_feed.xml",
    }


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test options flow."""
    entry = create_mock_entry(VALID_CONFIG_DEFAULT)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MAX_ENTRIES: 10,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_MAX_ENTRIES: 10,
    }


@pytest.mark.parametrize(
    ("fixture_name", "expected_title"),
    [
        ("feed_htmlentities", "RSS en español"),
        ("feed_atom_htmlentities", "ATOM RSS en español"),
    ],
)
async def test_feed_htmlentities(
    hass: HomeAssistant,
    feedparser,
    setup_entry,
    fixture_name,
    expected_title,
    request: pytest.FixtureRequest,
) -> None:
    """Test starting a flow by user from a feed with HTML Entities in the title."""
    with patch(
        "homeassistant.components.feedreader.config_flow.feedparser.http.get",
        side_effect=[request.getfixturevalue(fixture_name)],
    ):
        # init user flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        # success
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_URL: URL}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == expected_title
