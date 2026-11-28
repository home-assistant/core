"""Tests for the TCP entities."""

import ssl
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.sensor import SCAN_INTERVAL
from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

PLATFORMS = [
    ("binary_sensor", {"value_on": "7.on"}, STATE_OFF),
    ("sensor", {}, "7.123"),
]


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.parametrize(("platform", "extra", "expected"), PLATFORMS)
@pytest.mark.parametrize(
    ("method", "side_effect", "use_ssl"),
    [
        ("connect", OSError("Boom"), False),
        ("send", OSError("Boom"), False),
        ("recv", OSError("Boom"), False),
        ("recv", TimeoutError, False),
        ("recv", ssl.SSLError("Boom"), True),
        ("wrap_socket", ssl.SSLError("Boom"), True),
    ],
)
async def test_update_failure_after_success(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_create_connection: MagicMock,
    mock_socket: MagicMock,
    mock_ssl_context: MagicMock,
    setup_tcp,
    platform: str,
    extra: dict[str, str],
    expected: str,
    method: str,
    side_effect: Exception | type[Exception],
    use_ssl: bool,
) -> None:
    """Test failures make the entity unavailable and it recovers."""
    mock_ssl_context.return_value.wrap_socket.return_value = mock_socket
    await setup_tcp(ssl=use_ssl, **extra)
    assert hass.states.get(f"{platform}.test_name").state == expected

    failing = {
        "connect": mock_create_connection,
        "send": mock_socket.sendall,
        "recv": mock_socket.recv,
        "wrap_socket": mock_ssl_context.return_value.wrap_socket,
    }[method]
    failing.side_effect = side_effect
    await _poll(hass, freezer)
    assert hass.states.get(f"{platform}.test_name").state == STATE_UNAVAILABLE

    failing.side_effect = None
    await _poll(hass, freezer)
    assert hass.states.get(f"{platform}.test_name").state == expected


@pytest.mark.parametrize(
    ("platform", "extra"), [("binary_sensor", {"value_on": "7.on"}), ("sensor", {})]
)
async def test_initial_failure(
    hass: HomeAssistant,
    mock_create_connection: MagicMock,
    setup_tcp,
    platform: str,
    extra: dict[str, str],
) -> None:
    """Test a failure on the first update."""
    mock_create_connection.side_effect = OSError("Boom")
    await setup_tcp(**extra)
    assert hass.states.get(f"{platform}.test_name").state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("platform", "extra", "expected"),
    [("binary_sensor", {"value_on": "7.on"}, STATE_OFF), ("sensor", {}, "123")],
)
async def test_template_error_keeps_state(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_create_connection: MagicMock,
    mock_socket: MagicMock,
    setup_tcp,
    platform: str,
    extra: dict[str, str],
    expected: str,
) -> None:
    """Test template errors keep state and availability."""
    await setup_tcp(value_template="{{ value | int }}", **extra)

    mock_socket.recv.return_value = b"invalid"
    await _poll(hass, freezer)
    assert hass.states.get(f"{platform}.test_name").state == expected

    mock_create_connection.side_effect = OSError("Boom")
    await _poll(hass, freezer)
    assert hass.states.get(f"{platform}.test_name").state == STATE_UNAVAILABLE

    mock_create_connection.side_effect = None
    await _poll(hass, freezer)
    assert hass.states.get(f"{platform}.test_name").state == expected
