"""Test the telegram bot event platform."""

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.telegram_bot.const import (
    ATTR_MESSAGE,
    ATTR_TARGET,
    DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_send_message(
    hass: HomeAssistant,
    mock_broadcast_config_entry: MockConfigEntry,
    mock_external_calls: None,
    snapshot: SnapshotAssertion,
) -> None:
    """Test send message for entries with multiple chat_ids."""

    mock_broadcast_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_broadcast_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        {ATTR_TARGET: 123456, ATTR_MESSAGE: "test message"},
        blocking=True,
        return_response=True,
    )

    await hass.async_block_till_done()

    state = hass.states.get("event.mock_title_update_event")
    assert state.attributes == snapshot(exclude=props("config_entry_id"))
