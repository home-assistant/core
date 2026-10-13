"""The tests for the TCP sensor platform."""

from collections.abc import Callable
from copy import copy
import ssl
from unittest.mock import MagicMock, call, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.sensor import SCAN_INTERVAL
from homeassistant.components.tcp import common as tcp
from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component, async_fire_time_changed

TEST_CONFIG = {
    "sensor": {
        "platform": "tcp",
        tcp.CONF_NAME: "test_name",
        tcp.CONF_HOST: "test_host",
        tcp.CONF_PORT: 12345,
        tcp.CONF_TIMEOUT: tcp.DEFAULT_TIMEOUT + 1,
        tcp.CONF_PAYLOAD: "test_payload",
        tcp.CONF_UNIT_OF_MEASUREMENT: "test_unit",
        tcp.CONF_VALUE_TEMPLATE: "{{ '7.' + value }}",
        tcp.CONF_VALUE_ON: "7.on",
        tcp.CONF_BUFFER_SIZE: tcp.DEFAULT_BUFFER_SIZE + 1,
    }
}
SENSOR_TEST_CONFIG = TEST_CONFIG["sensor"]
TEST_ENTITY = "sensor.test_name"

KEYS_AND_DEFAULTS = {
    tcp.CONF_NAME: tcp.DEFAULT_NAME,
    tcp.CONF_TIMEOUT: tcp.DEFAULT_TIMEOUT,
    tcp.CONF_UNIT_OF_MEASUREMENT: None,
    tcp.CONF_VALUE_TEMPLATE: None,
    tcp.CONF_VALUE_ON: None,
    tcp.CONF_BUFFER_SIZE: tcp.DEFAULT_BUFFER_SIZE,
}

socket_test_value = "123"


@pytest.fixture(name="mock_socket")
def mock_socket_fixture(mock_select):
    """Mock socket."""
    with patch("homeassistant.components.tcp.entity.socket.socket") as mock_socket:
        socket_instance = mock_socket.return_value.__enter__.return_value
        socket_instance.recv.return_value = socket_test_value.encode()
        yield socket_instance


@pytest.fixture(name="mock_select")
def mock_select_fixture():
    """Mock select."""
    with patch(
        "homeassistant.components.tcp.entity.select.select",
        return_value=(True, False, False),
    ) as mock_select:
        yield mock_select


@pytest.fixture(name="mock_ssl_context")
def mock_ssl_context_fixture():
    """Mock select."""
    with patch(
        "homeassistant.components.tcp.entity.ssl.create_default_context",
    ) as mock_ssl_context:
        mock_ssl_context.return_value.wrap_socket.return_value.recv.return_value = (
            socket_test_value + "567"
        ).encode()
        yield mock_ssl_context


async def test_setup_platform_valid_config(hass: HomeAssistant, mock_socket) -> None:
    """Check a valid configuration and call add_entities with sensor."""
    with assert_setup_component(1, "sensor"):
        assert await async_setup_component(hass, "sensor", TEST_CONFIG)
        await hass.async_block_till_done()


async def test_setup_platform_invalid_config(hass: HomeAssistant, mock_socket) -> None:
    """Check an invalid configuration."""
    with assert_setup_component(0):
        assert await async_setup_component(
            hass, "sensor", {"sensor": {"platform": "tcp", "porrt": 1234}}
        )
        await hass.async_block_till_done()


async def test_state(hass: HomeAssistant, mock_socket, mock_select) -> None:
    """Return the contents of _state."""
    assert await async_setup_component(hass, "sensor", TEST_CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY)

    assert state
    assert state.state == "7.123"
    assert (
        state.attributes["unit_of_measurement"]
        == SENSOR_TEST_CONFIG[tcp.CONF_UNIT_OF_MEASUREMENT]
    )
    assert mock_socket.connect.called
    assert mock_socket.connect.call_args == call(
        (SENSOR_TEST_CONFIG["host"], SENSOR_TEST_CONFIG["port"])
    )
    assert mock_socket.send.called
    assert mock_socket.send.call_args == call(SENSOR_TEST_CONFIG["payload"].encode())
    assert mock_select.call_args == call(
        [mock_socket], [], [], SENSOR_TEST_CONFIG[tcp.CONF_TIMEOUT]
    )
    assert mock_socket.recv.called
    assert mock_socket.recv.call_args == call(SENSOR_TEST_CONFIG["buffer_size"])


async def test_config_uses_defaults(hass: HomeAssistant, mock_socket) -> None:
    """Check if defaults were set."""
    config = copy(SENSOR_TEST_CONFIG)

    for key in KEYS_AND_DEFAULTS:
        del config[key]

    with assert_setup_component(1) as result_config:
        assert await async_setup_component(hass, "sensor", {"sensor": config})
        await hass.async_block_till_done()

    state = hass.states.get("sensor.tcp_sensor")

    assert state
    assert state.state == "123"

    for key, default in KEYS_AND_DEFAULTS.items():
        assert result_config["sensor"][0].get(key) == default


@pytest.mark.parametrize("sock_attr", ["connect", "send"])
@pytest.mark.parametrize("platform", ["sensor", "binary_sensor"])
async def test_update_socket_error(
    hass: HomeAssistant, mock_socket: MagicMock, sock_attr: str, platform: str
) -> None:
    """Test socket errors during update."""
    socket_method = getattr(mock_socket, sock_attr)
    socket_method.side_effect = OSError("Boom")

    assert await async_setup_component(hass, platform, {platform: SENSOR_TEST_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get(f"{platform}.test_name")

    assert state
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("platform", ["sensor", "binary_sensor"])
async def test_update_select_fails(
    hass: HomeAssistant, mock_socket: MagicMock, mock_select: MagicMock, platform: str
) -> None:
    """Test select fails to return a socket for reading."""
    mock_select.return_value = (False, False, False)

    assert await async_setup_component(hass, platform, {platform: SENSOR_TEST_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get(f"{platform}.test_name")

    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_update_returns_if_template_render_fails(
    hass: HomeAssistant, mock_socket
) -> None:
    """Return None if rendering the template fails."""
    config = copy(SENSOR_TEST_CONFIG)
    config[tcp.CONF_VALUE_TEMPLATE] = "{{ value / 0 }}"

    assert await async_setup_component(hass, "sensor", {"sensor": config})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY)

    assert state
    assert state.state == "unknown"


async def test_ssl_state(
    hass: HomeAssistant, mock_socket, mock_select, mock_ssl_context
) -> None:
    """Return the contents of _state, updated over SSL."""
    config = copy(SENSOR_TEST_CONFIG)
    config[tcp.CONF_SSL] = "on"

    assert await async_setup_component(hass, "sensor", {"sensor": config})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY)

    assert state
    assert state.state == "7.123567"
    assert mock_socket.connect.called
    assert mock_socket.connect.call_args == call(
        (SENSOR_TEST_CONFIG["host"], SENSOR_TEST_CONFIG["port"])
    )
    assert not mock_socket.send.called
    assert mock_ssl_context.called
    assert mock_ssl_context.return_value.check_hostname
    mock_ssl_socket = mock_ssl_context.return_value.wrap_socket.return_value
    assert mock_ssl_socket.send.called
    assert mock_ssl_socket.send.call_args == call(
        SENSOR_TEST_CONFIG["payload"].encode()
    )
    assert mock_select.call_args == call(
        [mock_ssl_socket], [], [], SENSOR_TEST_CONFIG[tcp.CONF_TIMEOUT]
    )
    assert mock_ssl_socket.recv.called
    assert mock_ssl_socket.recv.call_args == call(SENSOR_TEST_CONFIG["buffer_size"])


async def test_ssl_state_verify_off(
    hass: HomeAssistant, mock_socket, mock_select, mock_ssl_context
) -> None:
    """Return the contents of _state, updated over SSL (verify_ssl disabled)."""
    config = copy(SENSOR_TEST_CONFIG)
    config[tcp.CONF_SSL] = "on"
    config[tcp.CONF_VERIFY_SSL] = "off"

    assert await async_setup_component(hass, "sensor", {"sensor": config})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY)

    assert state
    assert state.state == "7.123567"
    assert mock_socket.connect.called
    assert mock_socket.connect.call_args == call(
        (SENSOR_TEST_CONFIG["host"], SENSOR_TEST_CONFIG["port"])
    )
    assert not mock_socket.send.called
    assert mock_ssl_context.called
    assert not mock_ssl_context.return_value.check_hostname
    mock_ssl_socket = mock_ssl_context.return_value.wrap_socket.return_value
    assert mock_ssl_socket.send.called
    assert mock_ssl_socket.send.call_args == call(
        SENSOR_TEST_CONFIG["payload"].encode()
    )
    assert mock_select.call_args == call(
        [mock_ssl_socket], [], [], SENSOR_TEST_CONFIG[tcp.CONF_TIMEOUT]
    )
    assert mock_ssl_socket.recv.called
    assert mock_ssl_socket.recv.call_args == call(SENSOR_TEST_CONFIG["buffer_size"])


@pytest.mark.parametrize(
    ("platform", "expected"), [("sensor", "7.123"), ("binary_sensor", STATE_OFF)]
)
@pytest.mark.parametrize(
    ("method", "side_effect", "use_ssl"),
    [
        ("connect", OSError("Boom"), False),
        ("send", OSError("Boom"), False),
        ("select", lambda *args: (False, False, False), False),
        ("recv", OSError("Boom"), False),
        ("recv", ssl.SSLError("Boom"), True),
        ("wrap_socket", ssl.SSLError("Boom"), True),
    ],
)
async def test_update_failure_after_success(
    hass: HomeAssistant,
    mock_socket: MagicMock,
    mock_select: MagicMock,
    mock_ssl_context: MagicMock,
    freezer: FrozenDateTimeFactory,
    platform: str,
    expected: str,
    method: str,
    side_effect: OSError | Callable[..., tuple[bool, bool, bool]],
    use_ssl: bool,
) -> None:
    """Test connection failures, response timeouts, and recovery after a successful update."""
    mock_ssl_context.return_value.wrap_socket.return_value = mock_socket
    config = {**SENSOR_TEST_CONFIG, tcp.CONF_SSL: use_ssl}
    assert await async_setup_component(hass, platform, {platform: config})
    await hass.async_block_till_done()

    state = hass.states.get(f"{platform}.test_name")
    assert state
    assert state.state == expected

    failing_method = {
        "connect": mock_socket.connect,
        "send": mock_socket.send,
        "select": mock_select,
        "recv": mock_socket.recv,
        "wrap_socket": mock_ssl_context.return_value.wrap_socket,
    }[method]
    failing_method.side_effect = side_effect
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(f"{platform}.test_name")
    assert state
    assert state.state == STATE_UNAVAILABLE

    failing_method.side_effect = None
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(f"{platform}.test_name")
    assert state
    assert state.state == expected


@pytest.mark.parametrize(
    ("platform", "expected"), [("sensor", "123"), ("binary_sensor", STATE_OFF)]
)
async def test_template_error_after_success(
    hass: HomeAssistant,
    mock_socket: MagicMock,
    freezer: FrozenDateTimeFactory,
    platform: str,
    expected: str,
) -> None:
    """Test template errors preserve availability, including after reconnection."""
    config = {**SENSOR_TEST_CONFIG, tcp.CONF_VALUE_TEMPLATE: "{{ value | int }}"}
    assert await async_setup_component(hass, platform, {platform: config})
    await hass.async_block_till_done()

    mock_socket.recv.return_value = b"invalid"
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(f"{platform}.test_name")
    assert state
    assert state.state == expected

    mock_socket.connect.side_effect = OSError("Boom")
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(f"{platform}.test_name")
    assert state
    assert state.state == STATE_UNAVAILABLE

    mock_socket.connect.side_effect = None
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(f"{platform}.test_name")
    assert state
    assert state.state == expected


@pytest.mark.parametrize("platform", ["sensor", "binary_sensor"])
@pytest.mark.parametrize("method", ["wrap_socket", "recv"])
async def test_initial_ssl_failure(
    hass: HomeAssistant,
    mock_socket: MagicMock,
    mock_ssl_context: MagicMock,
    platform: str,
    method: str,
) -> None:
    """Test initial TLS handshake and receive failures mark entities unavailable."""
    mock_ssl_context.return_value.wrap_socket.return_value = mock_socket
    failing_method = {
        "wrap_socket": mock_ssl_context.return_value.wrap_socket,
        "recv": mock_socket.recv,
    }[method]
    failing_method.side_effect = ssl.SSLError("Boom")
    config = {**SENSOR_TEST_CONFIG, tcp.CONF_SSL: True}
    assert await async_setup_component(hass, platform, {platform: config})
    await hass.async_block_till_done()

    state = hass.states.get(f"{platform}.test_name")
    assert state
    assert state.state == STATE_UNAVAILABLE
