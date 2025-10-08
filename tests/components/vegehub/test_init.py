"""Tests for VegeHub integration setup and unload."""

from http import HTTPStatus
from unittest.mock import patch

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant

from . import init_integration
from .conftest import TEST_WEBHOOK_ID

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator


async def test_unload_entry(
    hass: HomeAssistant,
    mocked_config_entry: MockConfigEntry,
) -> None:
    """Test unloading the config entry."""
    with patch("homeassistant.components.vegehub.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mocked_config_entry)

    # Verify webhook is registered
    assert TEST_WEBHOOK_ID in hass.data["webhook"]

    # Unload the config entry
    assert await hass.config_entries.async_unload(mocked_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify webhook is unregistered
    assert TEST_WEBHOOK_ID not in hass.data["webhook"]


async def test_homeassistant_stop_unregisters_webhook(
    hass: HomeAssistant,
    mocked_config_entry: MockConfigEntry,
) -> None:
    """Test that webhook is unregistered when Home Assistant stops."""
    with patch("homeassistant.components.vegehub.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mocked_config_entry)

    # Verify webhook is registered
    assert TEST_WEBHOOK_ID in hass.data["webhook"]

    # Fire the stop event
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    # Verify webhook is unregistered
    assert TEST_WEBHOOK_ID not in hass.data["webhook"]


async def test_webhook_no_body(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mocked_config_entry: MockConfigEntry,
) -> None:
    """Test webhook handler with no body."""
    with patch("homeassistant.components.vegehub.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mocked_config_entry)

    assert TEST_WEBHOOK_ID in hass.data["webhook"], "Webhook was not registered"

    client = await hass_client_no_auth()

    # Send a POST request with no body
    resp = await client.post(f"/api/webhook/{TEST_WEBHOOK_ID}")

    # Should return BAD_REQUEST
    assert resp.status == HTTPStatus.BAD_REQUEST
    text = await resp.text()
    assert "No Body" in text
