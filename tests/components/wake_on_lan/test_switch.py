"""The tests for the wake on lan switch platform."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
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
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from tests.common import async_fire_time_changed, async_mock_service


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
    mac = "00:01:02:03:04:05"
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

    mac = dr.format_mac(mac)
    mock_send_magic_packet.assert_called_with(
        mac, ip_address=broadcast_address, port=port
    )


async def test_broadcast_config_ip(
    hass: HomeAssistant, mock_send_magic_packet: AsyncMock
) -> None:
    """Test with only broadcast address."""

    mac = "00:01:02:03:04:05"
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

    mac = dr.format_mac(mac)
    mock_send_magic_packet.assert_called_with(mac, ip_address=broadcast_address)


async def test_broadcast_config_port(
    hass: HomeAssistant, mock_send_magic_packet: AsyncMock
) -> None:
    """Test with only broadcast port config."""

    mac = "00:01:02:03:04:05"
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

    mac = dr.format_mac(mac)
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


async def test_on_grace_no_host(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that on grace period is not allowed when host is not set."""
    assert await async_setup_component(
        hass,
        switch.DOMAIN,
        {
            "switch": {
                "platform": "wake_on_lan",
                "mac": "00-01-02-03-04-05",
                "on_grace_period": 1,
            }
        },
    )
    assert hass.states.get("switch.wake_on_lan") is None
    assert "'on_grace_period' requires 'host' to be set." in caplog.text


async def test_off_grace_no_host(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that off grace period is not allowed when host is not set."""
    assert await async_setup_component(
        hass,
        switch.DOMAIN,
        {
            "switch": {
                "platform": "wake_on_lan",
                "mac": "00-01-02-03-04-05",
                "off_grace_period": 1,
            }
        },
    )
    assert hass.states.get("switch.wake_on_lan") is None
    assert "'off_grace_period' requires 'host' to be set." in caplog.text


async def test_off_grace_no_turn_off(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that off grace period is not allowed when turn_off is not set."""
    assert await async_setup_component(
        hass,
        switch.DOMAIN,
        {
            "switch": {
                "platform": "wake_on_lan",
                "mac": "00-01-02-03-04-05",
                "host": "validhostname",
                "off_grace_period": 1,
            }
        },
    )
    assert hass.states.get("switch.wake_on_lan") is None
    assert "'off_grace_period' requires 'turn_off' to be set." in caplog.text


async def test_on_grace_period(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_send_magic_packet: AsyncMock,
) -> None:
    """Test on grace period functionality."""
    assert await async_setup_component(
        hass,
        switch.DOMAIN,
        {
            "switch": {
                "scan_interval": timedelta(seconds=0.5),
                "platform": "wake_on_lan",
                "mac": "00-01-02-03-04-05",
                "host": "validhostname",
                "on_grace_period": 2,
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

    freezer.tick()
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("switch.wake_on_lan")
    assert state.state == STATE_ON

    freezer.tick()
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("switch.wake_on_lan")
    assert state.state == STATE_OFF


@pytest.mark.parametrize("subprocess_call_return_value", [0], indirect=True)
async def test_off_grace_period(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_send_magic_packet: AsyncMock,
    mock_subprocess_call: MagicMock,
) -> None:
    """Test off grace period functionality."""
    assert await async_setup_component(
        hass,
        switch.DOMAIN,
        {
            "switch": {
                "scan_interval": timedelta(seconds=0.5),
                "platform": "wake_on_lan",
                "mac": "00-01-02-03-04-05",
                "host": "validhostname",
                "turn_off": {"service": "shell_command.turn_off_target"},
                "off_grace_period": 2,
            }
        },
    )
    await hass.async_block_till_done()
    async_mock_service(hass, "shell_command", "turn_off_target")

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

    freezer.tick()
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("switch.wake_on_lan")
    assert state.state == STATE_OFF

    freezer.tick()
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("switch.wake_on_lan")
    assert state.state == STATE_ON
