"""Test IMAP diagnostics."""

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest

from homeassistant.components import imap
from homeassistant.components.sensor import SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import TEST_FETCH_RESPONSE_TEXT_PLAIN, TEST_SEARCH_RESPONSE
from .test_config_flow import MOCK_CONFIG

from tests.common import MockConfigEntry, async_capture_events, async_fire_time_changed
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.parametrize("imap_search", [TEST_SEARCH_RESPONSE])
@pytest.mark.parametrize("imap_fetch", [TEST_FETCH_RESPONSE_TEXT_PLAIN])
@pytest.mark.parametrize("imap_has_capability", [True, False], ids=["push", "poll"])
async def test_entry_diagnostics(
    hass: HomeAssistant,
    mock_imap_protocol: MagicMock,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test receiving a message successfully."""
    event_called = async_capture_events(hass, "imap_content")

    template = "{{ 4 * 4 }}"
    config = MOCK_CONFIG.copy()
    config["custom_event_data_template"] = template
    config_entry = MockConfigEntry(domain=imap.DOMAIN, data=config)

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    # Make sure we have had one update (when polling)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
    await hass.async_block_till_done()
    state = hass.states.get("sensor.imap_email_email_com")
    # we should have received one message
    assert state is not None
    assert state.state == "1"
    assert state.attributes["state_class"] == SensorStateClass.MEASUREMENT

    # we should have received one event
    assert len(event_called) == 1
    data: dict[str, Any] = event_called[0].data
    assert data["server"] == "imap.server.com"
    assert data["username"] == "email@email.com"
    assert data["search"] == "UnSeen UnDeleted"
    assert data["folder"] == "INBOX"
    assert data["sender"] == "john.doe@example.com"
    assert data["subject"] == "Test subject"

    await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    expected_config = {
        "username": "**REDACTED**",
        "password": "**REDACTED**",
        "server": "imap.server.com",
        "port": 993,
        "charset": "utf-8",
        "folder": "INBOX",
        "event_message_data": [
            "text",
            "headers",
        ],
        "search": "UnSeen UnDeleted",
        "custom_event_data_template": "{{ 4 * 4 }}",
    }
    expected_event_data = {
        "date": "2023-03-24T13:52:00+01:00",
        "initial": True,
        "custom_template_data_type": "<class 'int'>",
        "custom_template_result_length": 2,
    }
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )
    assert diagnostics["config"] == expected_config
    event_data = diagnostics["event"]
    assert event_data.pop("event_time") is not None
    assert event_data == expected_event_data
