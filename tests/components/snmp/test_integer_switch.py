"""SNMP switch tests."""

from unittest.mock import patch

from pysnmp.hlapi import Integer32

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_snmp_integer_switch_off(hass: HomeAssistant) -> None:
    """Test snmp switch returning int 0 for off."""

    config = {
        SWITCH_DOMAIN: {
            "platform": "snmp",
            "host": "192.168.1.32",
            # ippower-mib::ippoweroutlet1.0
            "baseoid": "1.3.6.1.4.1.38107.1.3.1.0",
            "payload_on": 1,
            "payload_off": 0,
        },
    }

    mock_data = Integer32(0)
    with patch(
        "homeassistant.components.snmp.switch.getCmd",
        return_value=(None, None, None, [[mock_data]]),
    ):
        assert await async_setup_component(hass, SWITCH_DOMAIN, config)
        await hass.async_block_till_done()
        state = hass.states.get("switch.snmp")
        assert state.state == "off"


async def test_snmp_integer_switch_on(hass: HomeAssistant) -> None:
    """Test snmp switch returning int 1 for on."""

    config = {
        SWITCH_DOMAIN: {
            "platform": "snmp",
            "host": "192.168.1.32",
            # ippower-mib::ippoweroutlet1.0
            "baseoid": "1.3.6.1.4.1.38107.1.3.1.0",
            "payload_on": 1,
            "payload_off": 0,
        },
    }

    mock_data = Integer32(1)
    with patch(
        "homeassistant.components.snmp.switch.getCmd",
        return_value=(None, None, None, [[mock_data]]),
    ):
        assert await async_setup_component(hass, SWITCH_DOMAIN, config)
        await hass.async_block_till_done()
        state = hass.states.get("switch.snmp")
        assert state.state == "on"
