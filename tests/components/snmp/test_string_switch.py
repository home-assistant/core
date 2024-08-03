"""SNMP switch tests."""

from unittest.mock import patch

from pysnmp.hlapi import OctetString

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_snmp_string_switch_off(hass: HomeAssistant) -> None:
    """Test snmp switch returning payload_off for off."""

    config = {
        SWITCH_DOMAIN: {
            "platform": "snmp",
            "host": "192.168.1.32",
            # ippower-mib::ippoweroutlet1.0
            "baseoid": "1.3.6.1.4.1.38107.1.3.1.0",
            "payload_on": "1,1,1,1",
            "payload_off": "0,0,0,0",
        },
    }

    mock_data = OctetString("0,0,0,0")
    with patch(
        "homeassistant.components.snmp.switch.getCmd",
        return_value=(None, None, None, [[mock_data]]),
    ):
        assert await async_setup_component(hass, SWITCH_DOMAIN, config)
        await hass.async_block_till_done()
        state = hass.states.get("switch.snmp")
        assert state.state == "off"


async def test_snmp_string_switch_on(hass: HomeAssistant) -> None:
    """Test snmp switch returning payload_on for on."""

    config = {
        SWITCH_DOMAIN: {
            "platform": "snmp",
            "host": "192.168.1.32",
            # ippower-mib::ippoweroutlet1.0
            "baseoid": "1.3.6.1.4.1.38107.1.3.1.0",
            "payload_on": "1,1,1,1",
            "payload_off": "0,0,0,0",
        },
    }

    mock_data = OctetString("1,1,1,1")
    with patch(
        "homeassistant.components.snmp.switch.getCmd",
        return_value=(None, None, None, [[mock_data]]),
    ):
        assert await async_setup_component(hass, SWITCH_DOMAIN, config)
        await hass.async_block_till_done()
        state = hass.states.get("switch.snmp")
        assert state.state == "on"


async def test_snmp_string_switch_unknown(hass: HomeAssistant) -> None:
    """Test snmp switch returning an unconfigured string for unknown."""

    config = {
        SWITCH_DOMAIN: {
            "platform": "snmp",
            "host": "192.168.1.32",
            # ippower-mib::ippoweroutlet1.0
            "baseoid": "1.3.6.1.4.1.38107.1.3.1.0",
            "payload_on": "1,1,1,1",
            "payload_off": "0,0,0,0",
        },
    }

    # This is a valid string for the state of 4 switches,
    # but HA is not capable of handling them as distinct switches currently
    mock_data = OctetString("1,0,1,0")
    with patch(
        "homeassistant.components.snmp.switch.getCmd",
        return_value=(None, None, None, [[mock_data]]),
    ):
        assert await async_setup_component(hass, SWITCH_DOMAIN, config)
        await hass.async_block_till_done()
        state = hass.states.get("switch.snmp")
        assert state.state == "unknown"
