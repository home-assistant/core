"""Tests for LCN events."""
from unittest.mock import patch

from pypck.inputs import ModSendKeysHost, ModStatusAccessControl
from pypck.lcn_addr import LcnAddr
from pypck.lcn_defs import AccessControlPeriphery, KeyAction, SendKeyCommand

from homeassistant.components.lcn import host_input_received
from homeassistant.helpers import device_registry as dr

from .conftest import MockPchkConnectionManager, init_integration

from tests.common import async_capture_events


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_fire_transponder_event(hass, entry):
    """Test the transponder event is fired."""
    await init_integration(hass, entry)
    device_registry = dr.async_get(hass)

    events = async_capture_events(hass, "lcn_transponder")

    inp = ModStatusAccessControl(
        LcnAddr(0, 7, False),
        periphery=AccessControlPeriphery.TRANSPONDER,
        code="aabbcc",
    )

    host_input_received(hass, entry, device_registry, inp)
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].event_type == "lcn_transponder"
    assert events[0].data["code"] == "aabbcc"


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_fire_fingerprint_event(hass, entry):
    """Test the fingerprint event is fired."""
    await init_integration(hass, entry)
    device_registry = dr.async_get(hass)

    events = async_capture_events(hass, "lcn_fingerprint")

    inp = ModStatusAccessControl(
        LcnAddr(0, 7, False),
        periphery=AccessControlPeriphery.FINGERPRINT,
        code="aabbcc",
    )

    host_input_received(hass, entry, device_registry, inp)
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].event_type == "lcn_fingerprint"
    assert events[0].data["code"] == "aabbcc"


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_fire_transmitter_event(hass, entry):
    """Test the transmitter event is fired."""
    await init_integration(hass, entry)
    device_registry = dr.async_get(hass)

    events = async_capture_events(hass, "lcn_transmitter")

    inp = ModStatusAccessControl(
        LcnAddr(0, 7, False),
        periphery=AccessControlPeriphery.TRANSMITTER,
        code="aabbcc",
        level=0,
        key=0,
        action=KeyAction.HIT,
    )

    host_input_received(hass, entry, device_registry, inp)
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].event_type == "lcn_transmitter"
    assert events[0].data["code"] == "aabbcc"
    assert events[0].data["level"] == 0
    assert events[0].data["key"] == 0
    assert events[0].data["action"] == "hit"


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_fire_sendkeys_event(hass, entry):
    """Test the sendkeys event is fired."""
    await init_integration(hass, entry)
    device_registry = dr.async_get(hass)

    events = async_capture_events(hass, "lcn_sendkeys")

    inp = ModSendKeysHost(
        LcnAddr(0, 7, False),
        actions=[SendKeyCommand.HIT, SendKeyCommand.MAKE, SendKeyCommand.DONTSEND],
        keys=[True, True, False, False, False, False, False, False],
    )

    host_input_received(hass, entry, device_registry, inp)
    await hass.async_block_till_done()

    assert len(events) == 4
    assert events[0].event_type == "lcn_sendkeys"
    assert events[0].data["key"] == "a1"
    assert events[0].data["action"] == "hit"
    assert events[1].event_type == "lcn_sendkeys"
    assert events[1].data["key"] == "a2"
    assert events[1].data["action"] == "hit"
    assert events[2].event_type == "lcn_sendkeys"
    assert events[2].data["key"] == "b1"
    assert events[2].data["action"] == "make"
    assert events[3].event_type == "lcn_sendkeys"
    assert events[3].data["key"] == "b2"
    assert events[3].data["action"] == "make"
