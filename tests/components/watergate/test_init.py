"""Tests for the Watergate integration init module."""

from collections.abc import Generator
from unittest.mock import patch

from homeassistant.components.valve import ValveState
from homeassistant.components.watergate.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import init_integration
from .const import MOCK_WEBHOOK_ID

from tests.common import ANY, AsyncMock, MockConfigEntry
from tests.typing import ClientSessionGenerator


async def test_async_setup_entry(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_watergate_client: Generator[AsyncMock],
) -> None:
    """Test setting up the Watergate integration."""
    hass.config.internal_url = "http://hassio.local"

    with (
        patch("homeassistant.components.watergate.async_register") as mock_webhook,
    ):
        await init_integration(hass, mock_entry)

        assert mock_entry.state is ConfigEntryState.LOADED

        mock_webhook.assert_called_once_with(
            hass,
            DOMAIN,
            "Watergate",
            MOCK_WEBHOOK_ID,
            ANY,
        )
        mock_watergate_client.async_set_webhook_url.assert_called_once_with(
            f"http://hassio.local/api/webhook/{MOCK_WEBHOOK_ID}"
        )
        mock_watergate_client.async_get_device_state.assert_called_once()


async def test_handle_webhook(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_entry: MockConfigEntry,
    mock_watergate_client: Generator[AsyncMock],
) -> None:
    """Test handling webhook events."""
    await init_integration(hass, mock_entry)

    entity_id = "valve.sonic"

    registered_entity = hass.states.get(entity_id)
    assert registered_entity
    assert registered_entity.state == ValveState.OPEN

    valve_change_data = {
        "type": "valve",
        "data": {"state": "closed"},
    }
    client = await hass_client_no_auth()
    await client.post(f"/api/webhook/{MOCK_WEBHOOK_ID}", json=valve_change_data)

    await hass.async_block_till_done()  # Ensure the webhook is processed

    assert hass.states.get(entity_id).state == ValveState.CLOSED

    valve_change_data = {
        "type": "valve",
        "data": {"state": "open"},
    }

    await client.post(f"/api/webhook/{MOCK_WEBHOOK_ID}", json=valve_change_data)

    await hass.async_block_till_done()  # Ensure the webhook is processed

    assert hass.states.get(entity_id).state == ValveState.OPEN
