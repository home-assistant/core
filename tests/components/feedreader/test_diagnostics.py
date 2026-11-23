"""Test the Feedreader diagnostics."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import load_fixture_bytes
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.feedreader.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import create_mock_entry
from .const import VALID_CONFIG_DEFAULT

MALFORMED_FEED = (
    b'<?xml version="1.0" encoding="UTF-8" ?>\n'
    b'<rss version="2.0"><channel><title>Private feed</title>'
    b"<item><title>Private entry</title>"
    b"<pubDate>Mon, 30 Apr 2018 15:10:00 +1000</pubDate></item>"
)


@pytest.mark.parametrize(
    "feed_data",
    [
        load_fixture_bytes("feedreader.xml", DOMAIN),
        load_fixture_bytes("feedreader7.xml", DOMAIN),
        MALFORMED_FEED,
    ],
    ids=["one_entry", "without_items", "malformed"],
)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    feed_data: bytes,
) -> None:
    """Test diagnostics."""
    entry = create_mock_entry(VALID_CONFIG_DEFAULT)
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.feedreader.coordinator.feedparser.http.get",
        return_value=feed_data,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot
