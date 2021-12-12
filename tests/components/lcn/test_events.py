"""Tests for LCN events."""
from unittest.mock import patch

from pypck.inputs import Input, ModSendKeysHost, ModStatusAccessControl
from pypck.lcn_addr import LcnAddr
from pypck.lcn_defs import AccessControlPeriphery, KeyAction, SendKeyCommand

from .conftest import MockPchkConnectionManager, init_integration

from tests.common import async_capture_events


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_fire_transponder_event(hass, entry):
    """Test the transponder event is fired."""
    await init_integration(hass, entry)

    events = async_capture_events(hass, "lcn_transponder")

    inp = ModStatusAccessControl(
        LcnAddr(0, 7, False),
        periphery=AccessControlPeriphery.TRANSPONDER,
        code="aabbcc",
    )

    lcn_connection = MockPchkConnectionManager.return_value
    await lcn_connection.async_process_input(inp)
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].event_type == "lcn_transponder"
    assert events[0].data["code"] == "aabbcc"


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_fire_fingerprint_event(hass, entry):
    """Test the fingerprint event is fired."""
    await init_integration(hass, entry)

    events = async_capture_events(hass, "lcn_fingerprint")

    inp = ModStatusAccessControl(
        LcnAddr(0, 7, False),
        periphery=AccessControlPeriphery.FINGERPRINT,
        code="aabbcc",
    )

    lcn_connection = MockPchkConnectionManager.return_value
    await lcn_connection.async_process_input(inp)
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].event_type == "lcn_fingerprint"
    assert events[0].data["code"] == "aabbcc"


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_fire_transmitter_event(hass, entry):
    """Test the transmitter event is fired."""
    await init_integration(hass, entry)

    events = async_capture_events(hass, "lcn_transmitter")

    inp = ModStatusAccessControl(
        LcnAddr(0, 7, False),
        periphery=AccessControlPeriphery.TRANSMITTER,
        code="aabbcc",
        level=0,
        key=0,
        action=KeyAction.HIT,
    )

    lcn_connection = MockPchkConnectionManager.return_value
    await lcn_connection.async_process_input(inp)
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].event_type == "lcn_transmitter"
    assert events[0].data["code"] == "aabbcc"
    assert events[0].data["level"] == 0
    assert events[0].data["key"] == 0
    assert events[0].data["action"] == "hit"


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_fire_sendkeys_event(hass, entry):
    """Test the send_keys event is fired."""
    await init_integration(hass, entry)

    events = async_capture_events(hass, "lcn_send_keys")

    inp = ModSendKeysHost(
        LcnAddr(0, 7, False),
        actions=[SendKeyCommand.HIT, SendKeyCommand.MAKE, SendKeyCommand.DONTSEND],
        keys=[True, True, False, False, False, False, False, False],
    )

    lcn_connection = MockPchkConnectionManager.return_value
    await lcn_connection.async_process_input(inp)
    await hass.async_block_till_done()

    assert len(events) == 4
    assert events[0].event_type == "lcn_send_keys"
    assert events[0].data["key"] == "a1"
    assert events[0].data["action"] == "hit"
    assert events[1].event_type == "lcn_send_keys"
    assert events[1].data["key"] == "a2"
    assert events[1].data["action"] == "hit"
    assert events[2].event_type == "lcn_send_keys"
    assert events[2].data["key"] == "b1"
    assert events[2].data["action"] == "make"
    assert events[3].event_type == "lcn_send_keys"
    assert events[3].data["key"] == "b2"
    assert events[3].data["action"] == "make"


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_dont_fire_on_non_module_input(hass, entry):
    """Test for no event is fired if a non-module input is received."""
    await init_integration(hass, entry)

    inp = Input()
    lcn_connection = MockPchkConnectionManager.return_value

    for event_name in (
        "lcn_transponder",
        "lcn_fingerprint",
        "lcn_transmitter",
        "lcn_send_keys",
    ):
        events = async_capture_events(hass, event_name)
        await lcn_connection.async_process_input(inp)
        await hass.async_block_till_done()
        assert len(events) == 0


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_dont_fire_on_unknown_module(hass, entry):
    """Test for no event is fired if an input from an unknown module is received."""
    await init_integration(hass, entry)

    inp = ModStatusAccessControl(
        LcnAddr(0, 10, False),  # unknown module
        periphery=AccessControlPeriphery.FINGERPRINT,
        code="aabbcc",
    )

    lcn_connection = MockPchkConnectionManager.return_value

    events = async_capture_events(hass, "lcn_transmitter")
    await lcn_connection.async_process_input(inp)
    await hass.async_block_till_done()
    assert len(events) == 0
