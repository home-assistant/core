"""Tests for the Withings component."""
from unittest.mock import patch

from withings_api.common import NotifyAppli

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import MockWithings, call_webhook
from .conftest import USER_ID, WEBHOOK_ID, ComponentSetup

from tests.typing import ClientSessionGenerator


async def test_binary_sensor(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test binary sensor."""
    await setup_integration()
    mock = MockWithings()
    with patch(
        "homeassistant.components.withings.common.ConfigEntryWithingsApi",
        return_value=mock,
    ):
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
