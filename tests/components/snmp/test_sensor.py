"""Tests for SNMP sensor platform setup behaviour."""

from unittest.mock import AsyncMock, patch

from pysnmp.proto.rfc1902 import Integer32

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.snmp.sensor import SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed

CONFIG = {
    SENSOR_DOMAIN: {
        "platform": "snmp",
        "host": "192.168.1.32",
        "baseoid": "1.3.6.1.4.1.2021.10.1.3.1",
    },
}


async def test_setup_fetches_once(hass: HomeAssistant) -> None:
    """Test setup performs only one SNMP fetch."""
    get_cmd = AsyncMock(return_value=(None, None, None, [[Integer32(13)]]))

    with patch("homeassistant.components.snmp.sensor.get_cmd", get_cmd):
        assert await async_setup_component(hass, SENSOR_DOMAIN, CONFIG)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.snmp").state == "13"
    assert get_cmd.call_count == 1


async def test_entity_recovers_when_device_unreachable(hass: HomeAssistant) -> None:
    """Test an entity unreachable at setup recovers on the next poll."""
    get_cmd = AsyncMock(
        side_effect=[
            ("No SNMP response received before timeout", None, None, None),
            (None, None, None, [[Integer32(13)]]),
        ]
    )

    with patch("homeassistant.components.snmp.sensor.get_cmd", get_cmd):
        assert await async_setup_component(hass, SENSOR_DOMAIN, CONFIG)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.snmp")
        assert state is not None
        assert state.state == "unknown"

        async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.snmp").state == "13"
