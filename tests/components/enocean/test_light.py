"""Tests for the EnOcean light platform."""

from enocean_async import BaseAddress
from enocean_async.protocol.erp1.rorg import RORG
from enocean_async.protocol.erp1.telegram import ERP1Telegram

from homeassistant.components.enocean import DOMAIN
from homeassistant.components.light import ATTR_BRIGHTNESS, DOMAIN as LIGHT_DOMAIN
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import TelegramReceiver


async def test_dimmer_status(
    hass: HomeAssistant, receive_telegram: TelegramReceiver
) -> None:
    """Test that a dimming telegram from a base address updates the light."""
    assert await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: [
                {
                    "platform": DOMAIN,
                    "id": [0xFF, 0x80, 0x00, 0x02],
                    "sender_id": [0xFF, 0x80, 0x00, 0x01],
                    "name": "dimmer",
                }
            ]
        },
    )
    await hass.async_block_till_done()

    await receive_telegram(
        ERP1Telegram(
            RORG.RORG_4BS, bytes.fromhex("02320009"), BaseAddress("FF:80:00:02")
        )
    )

    state = hass.states.get("light.dimmer")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 128
