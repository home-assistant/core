"""Tests for the Withings component."""
from unittest.mock import AsyncMock

from withings_api.common import NotifyAppli

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import call_webhook, enable_webhooks, setup_integration
from .conftest import USER_ID, WEBHOOK_ID

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator


async def test_binary_sensor(
    hass: HomeAssistant,
    withings: AsyncMock,
    disable_webhook_delay,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test binary sensor."""
    await enable_webhooks(hass)
    await setup_integration(hass, config_entry)

    client = await hass_client_no_auth()

    entity_id = "binary_sensor.henk_in_bed"

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    resp = await call_webhook(
        hass,
        WEBHOOK_ID,
        {"userid": USER_ID, "appli": NotifyAppli.BED_IN},
        client,
    )
    assert resp.message_code == 0
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON

    resp = await call_webhook(
        hass,
        WEBHOOK_ID,
        {"userid": USER_ID, "appli": NotifyAppli.BED_OUT},
        client,
    )
    assert resp.message_code == 0
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF
