"""Tests for the Cambridge Audio integration."""

from unittest.mock import AsyncMock

from aiostreammagic.models import CallbackType

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def mock_state_update(
    client: AsyncMock, callback_type: CallbackType = CallbackType.STATE
) -> None:
    """Trigger a callback in the media player."""
    for callback in client.register_state_update_callbacks.call_args_list:
        await callback[0][0](client, callback_type)
