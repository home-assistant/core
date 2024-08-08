"""SNMP switch tests."""

from unittest.mock import patch

from pysnmp.hlapi import Integer32, IpAddress, OctetString
import pytest

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

integer_config = {
    SWITCH_DOMAIN: {
        "platform": "snmp",
        "host": "192.168.1.32",
        # ippower-mib::ippoweroutlet1.0
        "baseoid": "1.3.6.1.4.1.38107.1.3.1.0",
        "payload_on": 1,
        "payload_off": 0,
    },
}

string_config = {
    SWITCH_DOMAIN: {
        "platform": "snmp",
        "host": "192.168.1.32",
        # DigiPower-PDU-MIB::pdu01OutletStatus.0
        "baseoid": "1.3.6.1.4.1.17420.1.2.9.1.13.0",
        "payload_on": "1,1,1,1",
        "payload_off": "0,0,0,0",
    },
}


async def test_snmp_integer_switch_off(hass: HomeAssistant) -> None:
    """Test snmp switch returning int 0 for off."""

    mock_data = Integer32(0)
    with patch(
        "homeassistant.components.snmp.switch.getCmd",
        return_value=(None, None, None, [[mock_data]]),
    ):
        assert await async_setup_component(hass, SWITCH_DOMAIN, integer_config)
        await hass.async_block_till_done()
        state = hass.states.get("switch.snmp")
        assert state.state == STATE_OFF


async def test_snmp_integer_switch_on(hass: HomeAssistant) -> None:
    """Test snmp switch returning int 1 for on."""

    mock_data = Integer32(1)
    with patch(
        "homeassistant.components.snmp.switch.getCmd",
        return_value=(None, None, None, [[mock_data]]),
    ):
        assert await async_setup_component(hass, SWITCH_DOMAIN, integer_config)
        await hass.async_block_till_done()
        state = hass.states.get("switch.snmp")
        assert state.state == STATE_ON


async def test_snmp_integer_switch_unknown(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test snmp switch returning int 3 (not a configured payload) for unknown."""

    mock_data = Integer32(3)
    with patch(
        "homeassistant.components.snmp.switch.getCmd",
        return_value=(None, None, None, [[mock_data]]),
    ):
        assert await async_setup_component(hass, SWITCH_DOMAIN, integer_config)
        await hass.async_block_till_done()
        state = hass.states.get("switch.snmp")
        assert state.state == STATE_UNKNOWN
        assert "Invalid payload '3' received for entity" in caplog.text


async def test_snmp_string_switch_off(hass: HomeAssistant) -> None:
    """Test snmp switch returning payload_off for off."""

    mock_data = OctetString("0,0,0,0")
    with patch(
        "homeassistant.components.snmp.switch.getCmd",
        return_value=(None, None, None, [[mock_data]]),
    ):
        assert await async_setup_component(hass, SWITCH_DOMAIN, string_config)
        await hass.async_block_till_done()
        state = hass.states.get("switch.snmp")
        assert state.state == STATE_OFF


async def test_snmp_string_switch_on(hass: HomeAssistant) -> None:
    """Test snmp switch returning payload_on for on."""

    mock_data = OctetString("1,1,1,1")
    with patch(
        "homeassistant.components.snmp.switch.getCmd",
        return_value=(None, None, None, [[mock_data]]),
    ):
        assert await async_setup_component(hass, SWITCH_DOMAIN, string_config)
        await hass.async_block_till_done()
        state = hass.states.get("switch.snmp")
        assert state.state == STATE_ON


async def test_snmp_string_switch_unknown(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test snmp switch returning an unconfigured string for unknown."""

    # This is a valid string for the state of 4 switches,
    # but HA is not yet capable of handling them as distinct switches
    mock_data = OctetString("1,0,1,0")
    with patch(
        "homeassistant.components.snmp.switch.getCmd",
        return_value=(None, None, None, [[mock_data]]),
    ):
        assert await async_setup_component(hass, SWITCH_DOMAIN, string_config)
        await hass.async_block_till_done()
        state = hass.states.get("switch.snmp")
        assert state.state == STATE_UNKNOWN
        assert "Invalid payload '1,0,1,0' received for entity" in caplog.text


async def test_snmp_string_switch_unknown_ipaddress(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test snmp switch returning an IpAddress for unknown."""

    # This is a valid IP Address SNMP response,
    # which we don't handle yet
    # (along with several other RFC1902 OBJECT-TYPEs)
    mock_data = IpAddress("127.0.0.1")
    with patch(
        "homeassistant.components.snmp.switch.getCmd",
        return_value=(None, None, None, [[mock_data]]),
    ):
        assert await async_setup_component(hass, SWITCH_DOMAIN, string_config)
        await hass.async_block_till_done()
        state = hass.states.get("switch.snmp")
        assert state.state == STATE_UNKNOWN
        assert "Invalid payload '\x7f\x00\x00\x01' received for entity" in caplog.text


async def test_snmp_string_switch_unknown_none(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test snmp switch returning None from somewhere in the pyasn1/pysnmp stack."""

    # OctetString can handle almost anything else
    with patch(
        "homeassistant.components.snmp.switch.getCmd",
        return_value=(None, None, None, [[None]]),
    ):
        assert await async_setup_component(hass, SWITCH_DOMAIN, string_config)
        await hass.async_block_till_done()
        state = hass.states.get("switch.snmp")
        assert state.state == STATE_UNKNOWN
        assert "Invalid payload 'None' received for entity" in caplog.text
