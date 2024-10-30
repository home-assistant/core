"""The tests for the feedreader config flow."""

from unittest.mock import Mock, patch
import urllib

import pytest

from homeassistant.components.feedreader import CONF_URLS
from homeassistant.components.feedreader.const import (
    CONF_MAX_ENTRIES,
    DEFAULT_MAX_ENTRIES,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_URL
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

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


@pytest.mark.parametrize(
    ("data", "expected_data", "expected_options"),
    [
        ({CONF_URLS: [URL]}, {CONF_URL: URL}, {CONF_MAX_ENTRIES: DEFAULT_MAX_ENTRIES}),
        (
            {CONF_URLS: [URL], CONF_MAX_ENTRIES: 5},
            {CONF_URL: URL},
            {CONF_MAX_ENTRIES: 5},
        ),
    ],
)
async def test_import(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    data,
    expected_data,
    expected_options,
    feedparser,
    setup_entry,
) -> None:
    """Test starting an import flow."""
    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert not config_entries

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: data})

    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert config_entries
    assert len(config_entries) == 1
    assert config_entries[0].title == FEED_TITLE
    assert config_entries[0].data == expected_data
    assert config_entries[0].options == expected_options

    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, "deprecated_yaml_feedreader"
    )


async def test_import_errors(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    feedparser,
    setup_entry,
    feed_one_event,
) -> None:
    """Test starting an import flow which results in an URL error."""
    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert not config_entries

    # raise URLError
    feedparser.side_effect = urllib.error.URLError("Test")
    feedparser.return_value = None
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_URLS: [URL]}})
    assert issue_registry.async_get_issue(
        DOMAIN,
        "import_yaml_error_feedreader_url_error_http_some_rss_local_rss_feed_xml",
    )


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
