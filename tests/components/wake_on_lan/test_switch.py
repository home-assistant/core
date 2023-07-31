"""The tests for the wake on lan switch platform."""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components import switch
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service


@pytest.fixture
def subprocess_call_return_value() -> int | None:
    """Return value for subprocess."""
    return 1


@pytest.fixture(autouse=True)
def mock_subprocess_call(
    subprocess_call_return_value: int,
) -> Generator[None, None, MagicMock]:
    """Mock magic packet."""
    with patch("homeassistant.components.wake_on_lan.switch.sp.call") as mock_sp:
        mock_sp.return_value = subprocess_call_return_value
        yield mock_sp


async def test_valid_hostname(
    hass: HomeAssistant, mock_send_magic_packet: AsyncMock
) -> None:
    """Test with valid hostname."""
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
    assert state.state == STATE_OFF

    with patch("homeassistant.components.wake_on_lan.switch.sp.call", return_value=0):
        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.wake_on_lan"},
            blocking=True,
        )

        state = hass.states.get("switch.wake_on_lan")
        assert state.state == STATE_ON

        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.wake_on_lan"},
            blocking=True,
        )

        state = hass.states.get("switch.wake_on_lan")
        assert state.state == STATE_ON


async def test_broadcast_config_ip_and_port(
    hass: HomeAssistant, mock_send_magic_packet: AsyncMock
) -> None:
    """Test with broadcast address and broadcast port config."""
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
    assert state.state == STATE_OFF

    await hass.services.async_call(
        switch.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.wake_on_lan"},
        blocking=True,
    )

    mock_send_magic_packet.assert_called_with(
        mac, ip_address=broadcast_address, port=port
    )


async def test_broadcast_config_ip(
    hass: HomeAssistant, mock_send_magic_packet: AsyncMock
) -> None:
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
    assert state.state == STATE_OFF

    await hass.services.async_call(
        switch.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.wake_on_lan"},
        blocking=True,
    )

    mock_send_magic_packet.assert_called_with(mac, ip_address=broadcast_address)


async def test_broadcast_config_port(
    hass: HomeAssistant, mock_send_magic_packet: AsyncMock
) -> None:
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
    assert state.state == STATE_OFF

    await hass.services.async_call(
        switch.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.wake_on_lan"},
        blocking=True,
    )

    mock_send_magic_packet.assert_called_with(mac, port=port)


async def test_off_script(
    hass: HomeAssistant, mock_send_magic_packet: AsyncMock
) -> None:
    """Test with turn off script."""

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
    assert state.state == STATE_OFF

    with patch("homeassistant.components.wake_on_lan.switch.sp.call", return_value=0):
        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.wake_on_lan"},
            blocking=True,
        )

        state = hass.states.get("switch.wake_on_lan")
        assert state.state == STATE_ON
        assert len(calls) == 0

    with patch("homeassistant.components.wake_on_lan.switch.sp.call", return_value=1):
        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.wake_on_lan"},
            blocking=True,
        )

        state = hass.states.get("switch.wake_on_lan")
        assert state.state == STATE_OFF
        assert len(calls) == 1


async def test_no_hostname_state(
    hass: HomeAssistant, mock_send_magic_packet: AsyncMock
) -> None:
    """Test that the state updates if we do not pass in a hostname."""

    assert await async_setup_component(
        hass,
        switch.DOMAIN,
        {
            "switch": {
                "platform": "wake_on_lan",
                "mac": "00-01-02-03-04-05",
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.wake_on_lan")
    assert state.state == STATE_OFF

    await hass.services.async_call(
        switch.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.wake_on_lan"},
        blocking=True,
    )

    state = hass.states.get("switch.wake_on_lan")
    assert state.state == STATE_ON

    await hass.services.async_call(
        switch.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.wake_on_lan"},
        blocking=True,
    )

    state = hass.states.get("switch.wake_on_lan")
    assert state.state == STATE_OFF
