"""SNMP tests."""

from unittest.mock import patch

from pysnmp.hlapi.asyncio import SnmpEngine
from pysnmp.hlapi.asyncio.cmdgen import lcd

from homeassistant.components import snmp
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant


async def test_async_get_snmp_engine(hass: HomeAssistant) -> None:
    """Test async_get_snmp_engine."""
    engine = await snmp.async_get_snmp_engine(hass)
    assert isinstance(engine, SnmpEngine)
    engine2 = await snmp.async_get_snmp_engine(hass)
    assert engine is engine2
    with patch.object(lcd, "unconfigure") as mock_unconfigure:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()
    assert mock_unconfigure.called
