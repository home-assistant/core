"""Tests for the EnOcean sensor platform."""

from enocean_async import EURID
from enocean_async.protocol.erp1.rorg import RORG
from enocean_async.protocol.erp1.telegram import ERP1Telegram
import pytest

from homeassistant.components.enocean import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import TelegramReceiver


@pytest.mark.parametrize(
    ("data", "expected_state"),
    [
        pytest.param("0000640c", "100.0", id="current_value"),
        pytest.param("00006408", STATE_UNKNOWN, id="cumulative_value_ignored"),
    ],
)
async def test_power_sensor(
    hass: HomeAssistant,
    receive_telegram: TelegramReceiver,
    data: str,
    expected_state: str,
) -> None:
    """Test that a meter reading telegram updates the power sensor."""
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: [
                {
                    "platform": DOMAIN,
                    "id": [0xDE, 0xAD, 0xBE, 0xEF],
                    "name": "meter",
                    "device_class": "powersensor",
                }
            ]
        },
    )
    await hass.async_block_till_done()

    await receive_telegram(
        ERP1Telegram(RORG.RORG_4BS, bytes.fromhex(data), EURID("DE:AD:BE:EF"))
    )

    assert hass.states.get("sensor.power_meter").state == expected_state
