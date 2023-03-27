"""Test the imap coordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.imap import DOMAIN
from homeassistant.core import Event, HomeAssistant
from homeassistant.util.dt import utcnow

from .conftest import AUTH, NONAUTH, SELECTED
from .const import TEST_FETCH_RESPONSE, TEST_SEARCH_RESPONSE
from .test_config_flow import MOCK_CONFIG

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize(
    ("imap_search", "imap_fetch"), [(TEST_SEARCH_RESPONSE, TEST_FETCH_RESPONSE)]
)
@pytest.mark.parametrize("imap_capabilities", [{"IDLE"}, set()], ids=["push", "poll"])
async def test_receiving_message_successfully(
    hass: HomeAssistant, mock_imap_protocol: dict[str, AsyncMock]
) -> None:
    """Test receiving a message successfully."""
    event_called = MagicMock()

    async def _async_event_listener(event: Event) -> None:
        """Listen to events."""
        event_called(event)

    handler = hass.bus.async_listen("imap_content", _async_event_listener)

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    # Make sure we have had one update (when polling)
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=5))
    await hass.async_block_till_done()
    state = hass.states.get("sensor.imap_email_email_com")
    # we should have received one message
    assert state is not None
    assert state.state == "1"

    # cleanup event listener
    handler()

    # we should have received one event
    event_called.assert_called_once()


@pytest.mark.parametrize("imap_capabilities", [{"IDLE"}, set()], ids=["push", "poll"])
@pytest.mark.parametrize(
    ("imap_login_state", "success"), [(AUTH, True), (NONAUTH, False)]
)
async def test_initial_authentication_error(
    hass: HomeAssistant, mock_imap_protocol: dict[str, AsyncMock], success: bool
) -> None:
    """Test authentication error."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id) == success
    await hass.async_block_till_done()


@pytest.mark.parametrize("imap_capabilities", [{"IDLE"}, set()], ids=["push", "poll"])
@pytest.mark.parametrize(
    ("imap_select_state", "success"), [(AUTH, False), (SELECTED, True)]
)
async def test_initial_invalid_folder_error(
    hass: HomeAssistant, mock_imap_protocol: dict[str, AsyncMock], success: bool
) -> None:
    """Test receiving a message successfully."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id) == success
    await hass.async_block_till_done()
