"""Tests for Clicky init."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.components.clicky.const import CONF_SITE_ID, CONF_SITEKEY, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .common import _make_report

from tests.common import MockConfigEntry


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test async_setup_entry."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SITE_ID: "12345",
            CONF_SITEKEY: "abcdef",
        },
    )

    entry.add_to_hass(hass)

    with (
        patch(
            "pyclicky.ClickyClient.visitors_online",
            AsyncMock(return_value=_make_report(5)),
        ),
        patch(
            "pyclicky.ClickyClient.time_total",
            AsyncMock(return_value=_make_report(120)),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
