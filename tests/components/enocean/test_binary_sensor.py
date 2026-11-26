"""Tests for the EnOcean binary sensor platform."""

from enocean_async import EURID
from enocean_async.protocol.erp1.rorg import RORG
from enocean_async.protocol.erp1.telegram import ERP1Telegram
import pytest
from pytest_homeassistant.common import async_capture_events

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.enocean import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import TelegramReceiver

DEVICE_ID = [0xDE, 0xAD, 0xBE, 0xEF]


@pytest.mark.parametrize(
    ("data", "status", "expected"),
    [
        pytest.param(
            b"\x70", 0x30, {"pushed": 1, "which": 0, "onoff": 0}, id="pressed"
        ),
        pytest.param(
            b"\x10", 0x30, {"pushed": 1, "which": 1, "onoff": 1}, id="other_button"
        ),
        pytest.param(
            b"\x00", 0x20, {"pushed": 0, "which": -1, "onoff": -1}, id="released"
        ),
    ],
)
async def test_button_event(
    hass: HomeAssistant,
    receive_telegram: TelegramReceiver,
    data: bytes,
    status: int,
    expected: dict[str, int],
) -> None:
    """Test that a rocker switch telegram fires a button event."""
    assert await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: [
                {"platform": DOMAIN, "id": DEVICE_ID, "name": "button"}
            ]
        },
    )
    await hass.async_block_till_done()
    events = async_capture_events(hass, "button_pressed")

    await receive_telegram(
        ERP1Telegram(RORG.RORG_RPS, data, EURID("DE:AD:BE:EF"), status)
    )

    assert len(events) == 1
    assert events[0].data == {"id": DEVICE_ID, **expected}
