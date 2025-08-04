"""Tests for the Feedreader services."""

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.feedreader.const import ATTR_CONFIG_ENTRY_ID, DOMAIN
from homeassistant.components.feedreader.services import SERVICE_GET_POSTS
from homeassistant.core import HomeAssistant

from . import create_mock_entry
from .const import VALID_CONFIG_DEFAULT


async def test_get_posts(
    hass: HomeAssistant, feed_one_event, snapshot: SnapshotAssertion
) -> None:
    """Test the get_posts service."""
    entry = create_mock_entry(VALID_CONFIG_DEFAULT)
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.feedreader.coordinator.feedparser.http.get",
        return_value=feed_one_event,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_POSTS,
        {
            ATTR_CONFIG_ENTRY_ID: entry.entry_id,
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot
