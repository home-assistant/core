"""Tests for the feedreader component."""

from typing import Any
from unittest.mock import patch

from homeassistant.components.feedreader.const import CONF_MAX_ENTRIES, DOMAIN
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


def load_fixture_bytes(src: str) -> bytes:
    """Return byte stream of fixture."""
    feed_data = load_fixture(src, DOMAIN)
    return bytes(feed_data, "utf-8")


def create_mock_entry(
    data: dict[str, Any],
) -> MockConfigEntry:
    """Create config entry mock from data."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: data[CONF_URL]},
        options={CONF_MAX_ENTRIES: data[CONF_MAX_ENTRIES]},
    )


async def async_setup_config_entry(
    hass: HomeAssistant,
    data: dict[str, Any],
    return_value: bytes | None = None,
    side_effect: bytes | None = None,
) -> bool:
    """Do setup of a MockConfigEntry."""
    entry = create_mock_entry(data)
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.feedreader.coordinator.feedparser.http.get",
    ) as feedparser:
        if return_value:
            feedparser.return_value = return_value
        if side_effect:
            feedparser.side_effect = side_effect
        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return result
