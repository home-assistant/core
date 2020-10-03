"""The tests for the wake on lan switch platform."""
import platform
import subprocess

import wakeonlan

import homeassistant.components.switch as switch
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.setup import async_setup_component

from tests.async_mock import Mock, patch
from tests.common import async_mock_service

TEST_STATE = None


send_magic_packet = Mock(return_value=None)


def call(cmd, stdout, stderr):
    """Return fake subprocess return codes."""
    if cmd[5] == "validhostname" and TEST_STATE:
        return 0
    return 2


def system():
    """Fake system call to test the windows platform."""
    return "Windows"


async def test_valid_hostname(hass):
    """Test with valid hostname."""
    global TEST_STATE
    TEST_STATE = False
    assert await async_setup_component(
        hass,
        switch.DOMAIN,
        {
            "switch": {
                "platform": "wake_on_lan",
                "mac": "00-01-02-03-04-05",
                "host": "validhostname",
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.wake_on_lan")
    assert STATE_OFF == state.state

    TEST_STATE = True

    with patch.object(
        wakeonlan, "send_magic_packet", new=send_magic_packet
    ), patch.object(subprocess, "call", new=call):

        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.wake_on_lan"},
            blocking=True,
        )

        state = hass.states.get("switch.wake_on_lan")
        assert STATE_ON == state.state

        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.wake_on_lan"},
            blocking=True,
        )

        state = hass.states.get("switch.wake_on_lan")
        assert STATE_ON == state.state


async def test_valid_hostname_windows(hass):
    """Test with valid hostname on windows."""
    global TEST_STATE
    TEST_STATE = False
    assert await async_setup_component(
        hass,
        switch.DOMAIN,
        {
            "switch": {
                "platform": "wake_on_lan",
                "mac": "00-01-02-03-04-05",
                "host": "validhostname",
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.wake_on_lan")
    assert STATE_OFF == state.state

    TEST_STATE = True

    with patch.object(
        wakeonlan, "send_magic_packet", new=send_magic_packet
    ), patch.object(subprocess, "call", new=call), patch.object(
        platform, "system", new=system
    ):
        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.wake_on_lan"},
            blocking=True,
        )

    state = hass.states.get("switch.wake_on_lan")
    assert STATE_ON == state.state


async def test_minimal_config(hass):
    """Test with minimal config."""

    assert await async_setup_component(
        hass,
        switch.DOMAIN,
        {"switch": {"platform": "wake_on_lan", "mac": "00-01-02-03-04-05"}},
    )


async def test_broadcast_config_ip_and_port(hass):
    """Test with broadcast address and broadcast port config."""
    global TEST_STATE
    TEST_STATE = False

    mac = "00-01-02-03-04-05"
    broadcast_address = "255.255.255.255"
    port = 999

    assert await async_setup_component(
        hass,
        switch.DOMAIN,
        {
            "switch": {
                "platform": "wake_on_lan",
                "mac": mac,
                "broadcast_address": broadcast_address,
                "broadcast_port": port,
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.wake_on_lan")
    assert STATE_OFF == state.state

    TEST_STATE = True

    with patch.object(
        wakeonlan, "send_magic_packet", new=send_magic_packet
    ), patch.object(subprocess, "call", new=call):

        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.wake_on_lan"},
            blocking=True,
        )

        send_magic_packet.assert_called_with(
            mac, ip_address=broadcast_address, port=port
        )


async def test_broadcast_config_ip(hass):
    """Test with only broadcast address."""

    mac = "00-01-02-03-04-05"
    broadcast_address = "255.255.255.255"

    assert await async_setup_component(
        hass,
        switch.DOMAIN,
        {
            "switch": {
                "platform": "wake_on_lan",
                "mac": mac,
                "broadcast_address": broadcast_address,
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.wake_on_lan")
    assert STATE_OFF == state.state

    with patch.object(
        wakeonlan, "send_magic_packet", new=send_magic_packet
    ), patch.object(subprocess, "call", new=call):

        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.wake_on_lan"},
            blocking=True,
        )

        send_magic_packet.assert_called_with(mac, ip_address=broadcast_address)


async def test_broadcast_config_port(hass):
    """Test with only broadcast port config."""

    mac = "00-01-02-03-04-05"
    port = 999

    assert await async_setup_component(
        hass,
        switch.DOMAIN,
        {"switch": {"platform": "wake_on_lan", "mac": mac, "broadcast_port": port}},
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.wake_on_lan")
    assert STATE_OFF == state.state

    with patch.object(
        wakeonlan, "send_magic_packet", new=send_magic_packet
    ), patch.object(subprocess, "call", new=call):

        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.wake_on_lan"},
            blocking=True,
        )

        send_magic_packet.assert_called_with(mac, port=port)


async def test_off_script(hass):
    """Test with turn off script."""
    global TEST_STATE
    TEST_STATE = False

    assert await async_setup_component(
        hass,
        switch.DOMAIN,
        {
            "switch": {
                "platform": "wake_on_lan",
                "mac": "00-01-02-03-04-05",
                "host": "validhostname",
                "turn_off": {"service": "shell_command.turn_off_target"},
            }
        },
    )
    await hass.async_block_till_done()
    calls = async_mock_service(hass, "shell_command", "turn_off_target")

    state = hass.states.get("switch.wake_on_lan")
    assert STATE_OFF == state.state

    TEST_STATE = True

    with patch.object(
        wakeonlan, "send_magic_packet", new=send_magic_packet
    ), patch.object(subprocess, "call", new=call):

        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.wake_on_lan"},
            blocking=True,
        )

        state = hass.states.get("switch.wake_on_lan")
        assert STATE_ON == state.state
        assert len(calls) == 0

        TEST_STATE = False

        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.wake_on_lan"},
            blocking=True,
        )

        state = hass.states.get("switch.wake_on_lan")
        assert STATE_OFF == state.state
        assert len(calls) == 1


async def test_invalid_hostname_windows(hass):
    """Test with invalid hostname on windows."""
    global TEST_STATE
    TEST_STATE = False

    assert await async_setup_component(
        hass,
        switch.DOMAIN,
        {
            "switch": {
                "platform": "wake_on_lan",
                "mac": "00-01-02-03-04-05",
                "host": "invalidhostname",
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.wake_on_lan")
    assert STATE_OFF == state.state

    TEST_STATE = True

    with patch.object(
        wakeonlan, "send_magic_packet", new=send_magic_packet
    ), patch.object(subprocess, "call", new=call):

        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.wake_on_lan"},
            blocking=True,
        )

        state = hass.states.get("switch.wake_on_lan")
        assert STATE_OFF == state.state
