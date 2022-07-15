"""Tests for LCN events."""
from pypck.inputs import Input, ModSendKeysHost, ModStatusAccessControl
from pypck.lcn_addr import LcnAddr
from pypck.lcn_defs import AccessControlPeriphery, KeyAction, SendKeyCommand

from tests.common import async_capture_events

LCN_TRANSPONDER = "lcn_transponder"
LCN_FINGERPRINT = "lcn_fingerprint"
LCN_TRANSMITTER = "lcn_transmitter"
LCN_SEND_KEYS = "lcn_send_keys"


async def test_fire_transponder_event(hass, lcn_connection):
    """Test the transponder event is fired."""
    events = async_capture_events(hass, LCN_TRANSPONDER)

    inp = ModStatusAccessControl(
        LcnAddr(0, 7, False),
        periphery=AccessControlPeriphery.TRANSPONDER,
        code="aabbcc",
    )

    await lcn_connection.async_process_input(inp)
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].event_type == LCN_TRANSPONDER
    assert events[0].data["code"] == "aabbcc"


async def test_fire_fingerprint_event(hass, lcn_connection):
    """Test the fingerprint event is fired."""
    events = async_capture_events(hass, LCN_FINGERPRINT)

    inp = ModStatusAccessControl(
        LcnAddr(0, 7, False),
        periphery=AccessControlPeriphery.FINGERPRINT,
        code="aabbcc",
    )

    await lcn_connection.async_process_input(inp)
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].event_type == LCN_FINGERPRINT
    assert events[0].data["code"] == "aabbcc"


async def test_fire_codelock_event(hass, lcn_connection):
    """Test the codelock event is fired."""
    events = async_capture_events(hass, "lcn_codelock")

    inp = ModStatusAccessControl(
        LcnAddr(0, 7, False),
        periphery=AccessControlPeriphery.CODELOCK,
        code="aabbcc",
    )

    await lcn_connection.async_process_input(inp)
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].event_type == "lcn_codelock"
    assert events[0].data["code"] == "aabbcc"


async def test_fire_transmitter_event(hass, lcn_connection):
    """Test the transmitter event is fired."""
    events = async_capture_events(hass, LCN_TRANSMITTER)

    inp = ModStatusAccessControl(
        LcnAddr(0, 7, False),
        periphery=AccessControlPeriphery.TRANSMITTER,
        code="aabbcc",
        level=0,
        key=0,
        action=KeyAction.HIT,
    )

    await lcn_connection.async_process_input(inp)
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].event_type == LCN_TRANSMITTER
    assert events[0].data["code"] == "aabbcc"
    assert events[0].data["level"] == 0
    assert events[0].data["key"] == 0
    assert events[0].data["action"] == "hit"


async def test_fire_sendkeys_event(hass, lcn_connection):
    """Test the send_keys event is fired."""
    events = async_capture_events(hass, LCN_SEND_KEYS)

    inp = ModSendKeysHost(
        LcnAddr(0, 7, False),
        actions=[SendKeyCommand.HIT, SendKeyCommand.MAKE, SendKeyCommand.DONTSEND],
        keys=[True, True, False, False, False, False, False, False],
    )

    await lcn_connection.async_process_input(inp)
    await hass.async_block_till_done()

    assert len(events) == 4
    assert events[0].event_type == LCN_SEND_KEYS
    assert events[0].data["key"] == "a1"
    assert events[0].data["action"] == "hit"
    assert events[1].event_type == LCN_SEND_KEYS
    assert events[1].data["key"] == "a2"
    assert events[1].data["action"] == "hit"
    assert events[2].event_type == LCN_SEND_KEYS
    assert events[2].data["key"] == "b1"
    assert events[2].data["action"] == "make"
    assert events[3].event_type == LCN_SEND_KEYS
    assert events[3].data["key"] == "b2"
    assert events[3].data["action"] == "make"


async def test_dont_fire_on_non_module_input(hass, lcn_connection):
    """Test for no event is fired if a non-module input is received."""
    inp = Input()

    for event_name in (
        LCN_TRANSPONDER,
        LCN_FINGERPRINT,
        LCN_TRANSMITTER,
        LCN_SEND_KEYS,
    ):
        events = async_capture_events(hass, event_name)
        await lcn_connection.async_process_input(inp)
        await hass.async_block_till_done()
        assert len(events) == 0


async def test_dont_fire_on_unknown_module(hass, lcn_connection):
    """Test for no event is fired if an input from an unknown module is received."""
    inp = ModStatusAccessControl(
        LcnAddr(0, 10, False),  # unknown module
        periphery=AccessControlPeriphery.FINGERPRINT,
        code="aabbcc",
    )

    events = async_capture_events(hass, LCN_FINGERPRINT)
    await lcn_connection.async_process_input(inp)
    await hass.async_block_till_done()
    assert len(events) == 0
