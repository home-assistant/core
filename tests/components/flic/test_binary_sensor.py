"""Tests for Flic button integration."""

import socket
import sys
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.const import CONF_DISCOVERY, CONF_HOST, CONF_PORT, CONF_TIMEOUT
from homeassistant.core import HomeAssistant


class MockClickType:
    """Mock ClickType enum."""

    ButtonDown = 0
    ButtonUp = 1
    ButtonClick = 2
    ButtonSingleClick = 3
    ButtonDoubleClick = 4
    ButtonHold = 5


class MockConnectionStatus:
    """Mock ConnectionStatus enum."""

    Disconnected = 0
    Connected = 1
    Ready = 2


class MockDisconnectReason:
    """Mock DisconnectReason enum."""

    Unspecified = 0


class MockScanWizardResult:
    """Mock ScanWizardResult enum."""

    WizardSuccess = 0
    WizardFailedTimeout = 2


class MockButtonConnectionChannel:
    """Mock ButtonConnectionChannel."""

    def __init__(self, address: str) -> None:
        """Initialize mock channel."""
        self.address = address
        self.on_button_up_or_down = None
        self.on_connection_status_changed = None
        self.on_button_click_or_hold = None
        self.on_button_single_or_double_click = None
        self.on_button_single_or_double_click_or_hold = None


class MockScanWizard:
    """Mock ScanWizard."""

    def __init__(self) -> None:
        """Initialize mock scan wizard."""
        self.on_completed = None


class MockFlicClient:
    """Mock FlicClient for testing."""

    def __init__(self, host: str = "localhost", port: int = 5551) -> None:
        """Initialize mock client."""
        self.host = host
        self.port = port
        self.addresses: tuple[str, ...] = ()
        self.get_info_callback: mock.MagicMock | None = None
        self.scan_wizard: mock.MagicMock | None = None
        self.channels: list = []
        self.on_new_verified_button = None
        self._closed = False
        self._sock = MagicMock()

    def close(self) -> None:
        """Close the client."""
        self._closed = True

    def get_info(self, callback) -> None:
        """Get info from server."""
        self.get_info_callback = callback
        callback({"bd_addr_of_verified_buttons": list(self.addresses)})

    def handle_events(self) -> None:
        """Handle events (blocks until closed)."""

    def add_scan_wizard(self, wizard) -> None:
        """Add scan wizard."""
        self.scan_wizard = wizard

    def add_connection_channel(self, channel) -> None:
        """Add connection channel."""
        self.channels.append(channel)


mock_pyflic = MagicMock()
mock_pyflic.ClickType = MockClickType
mock_pyflic.ConnectionStatus = MockConnectionStatus
mock_pyflic.DisconnectReason = MockDisconnectReason
mock_pyflic.ScanWizardResult = MockScanWizardResult
mock_pyflic.ButtonConnectionChannel = MockButtonConnectionChannel
mock_pyflic.ScanWizard = MockScanWizard
mock_pyflic.FlicClient = MockFlicClient
sys.modules["pyflic"] = mock_pyflic

from homeassistant.components.flic.binary_sensor import (  # noqa: E402
    CLICK_TYPE_DOUBLE,
    CLICK_TYPE_HOLD,
    CLICK_TYPE_SINGLE,
    EVENT_DATA_ADDRESS,
    EVENT_DATA_NAME,
    EVENT_DATA_QUEUED_TIME,
    EVENT_DATA_TYPE,
    EVENT_NAME,
    FlicButton,
    FlicConnectionManager,
)


async def test_button_uid(hass: HomeAssistant) -> None:
    """Test UID assignment for Flic buttons."""
    flic_client = MockFlicClient()

    button_lower = FlicButton(hass, flic_client, "80:e4:da:78:6e:11", 3, None)
    assert button_lower.unique_id == "80:e4:da:78:6e:11"
    assert button_lower.name == "flic_80e4da786e11"

    button_upper = FlicButton(hass, flic_client, "80:E4:DA:78:6E:12", 3, None)
    assert button_upper.unique_id == "80:e4:da:78:6e:12"
    assert button_upper.name == "flic_80E4DA786E12"


async def test_connection_manager_initial_connect(hass: HomeAssistant) -> None:
    """Test initial connection to flicd."""
    add_entities_mock = MagicMock()
    config = {
        CONF_HOST: "localhost",
        CONF_PORT: 5551,
        CONF_DISCOVERY: False,
        CONF_TIMEOUT: 3,
    }

    mock_pyflic.FlicClient = MockFlicClient

    manager = FlicConnectionManager(hass, "localhost", 5551, config, add_entities_mock)
    assert manager._connect()
    assert manager._client is not None


async def test_connection_manager_connect_failure(hass: HomeAssistant) -> None:
    """Test connection failure handling."""
    add_entities_mock = MagicMock()
    config = {
        CONF_HOST: "localhost",
        CONF_PORT: 5551,
        CONF_DISCOVERY: False,
        CONF_TIMEOUT: 3,
    }

    def raise_connection_refused(host: str, port: int):
        raise ConnectionRefusedError("Connection refused")

    mock_pyflic.FlicClient = raise_connection_refused

    manager = FlicConnectionManager(hass, "localhost", 5551, config, add_entities_mock)
    assert not manager._connect()
    assert manager._client is None


async def test_connection_manager_reconnect_backoff(hass: HomeAssistant) -> None:
    """Test exponential backoff during reconnection."""
    add_entities_mock = MagicMock()
    config = {
        CONF_HOST: "localhost",
        CONF_PORT: 5551,
        CONF_DISCOVERY: False,
        CONF_TIMEOUT: 3,
    }

    with patch("homeassistant.components.flic.binary_sensor.time.sleep") as mock_sleep:
        manager = FlicConnectionManager(
            hass, "localhost", 5551, config, add_entities_mock
        )
        manager._reconnect_attempts = 1
        manager._backoff_sleep()
        mock_sleep.assert_called_once_with(1)

        mock_sleep.reset_mock()
        manager._reconnect_attempts = 2
        manager._backoff_sleep()
        mock_sleep.assert_called_once_with(2)

        mock_sleep.reset_mock()
        manager._reconnect_attempts = 3
        manager._backoff_sleep()
        mock_sleep.assert_called_once_with(4)


async def test_connection_manager_backoff_caps_at_max(
    hass: HomeAssistant,
) -> None:
    """Test that backoff sleep caps at maximum value."""
    add_entities_mock = MagicMock()
    config = {
        CONF_HOST: "localhost",
        CONF_PORT: 5551,
        CONF_DISCOVERY: False,
        CONF_TIMEOUT: 3,
    }

    with patch("homeassistant.components.flic.binary_sensor.time.sleep") as mock_sleep:
        manager = FlicConnectionManager(
            hass, "localhost", 5551, config, add_entities_mock
        )
        manager._reconnect_attempts = 100
        manager._backoff_sleep()

        mock_sleep.assert_called_once_with(300)


async def test_connection_manager_successful_reconnect(hass: HomeAssistant) -> None:
    """Test successful reconnection resets attempt counter."""
    add_entities_mock = MagicMock()
    config = {
        CONF_HOST: "localhost",
        CONF_PORT: 5551,
        CONF_DISCOVERY: False,
        CONF_TIMEOUT: 3,
    }

    mock_pyflic.FlicClient = MockFlicClient

    manager = FlicConnectionManager(hass, "localhost", 5551, config, add_entities_mock)
    manager._reconnect_attempts = 5

    assert manager._connect()
    manager._reconnect_attempts = 0

    assert manager._reconnect_attempts == 0


async def test_connection_manager_restore_buttons(hass: HomeAssistant) -> None:
    """Test button channel restoration after reconnection."""
    flic_client = MockFlicClient()
    add_entities_mock = MagicMock()
    config = {
        CONF_HOST: "localhost",
        CONF_PORT: 5551,
        CONF_DISCOVERY: False,
        CONF_TIMEOUT: 3,
    }

    mock_pyflic.FlicClient = MockFlicClient

    manager = FlicConnectionManager(hass, "localhost", 5551, config, add_entities_mock)
    manager._client = flic_client

    button_mock = MagicMock(spec=FlicButton)
    button_mock.address = "80:e4:da:78:6e:11"
    manager._buttons.append(button_mock)

    manager._restore_buttons()

    button_mock.restore_channel.assert_called_once_with(flic_client)


async def test_connection_manager_setup_button_deduplication(
    hass: HomeAssistant,
) -> None:
    """Test that duplicate button addresses are not added."""
    flic_client = MockFlicClient()
    entities_added: list = []

    def capture_entities(entities: list) -> None:
        entities_added.extend(entities)

    config = {
        CONF_HOST: "localhost",
        CONF_PORT: 5551,
        CONF_DISCOVERY: False,
        CONF_TIMEOUT: 3,
    }

    mock_pyflic.FlicClient = MockFlicClient

    manager = FlicConnectionManager(hass, "localhost", 5551, config, capture_entities)
    manager._client = flic_client

    manager._setup_button("80:e4:da:78:6e:11")
    manager._setup_button("80:e4:da:78:6e:11")

    assert len(entities_added) == 1
    assert len(manager._known_addresses) == 1


async def test_button_click_event(hass: HomeAssistant) -> None:
    """Test that button click events are fired correctly."""
    flic_client = MockFlicClient()
    events: list = []

    def capture_event(event):
        events.append(event)

    hass.bus.async_listen(EVENT_NAME, capture_event)

    button = FlicButton(hass, flic_client, "80:e4:da:78:6e:11", 3, None)

    button._on_click(
        MagicMock(),
        MockClickType.ButtonSingleClick,
        False,
        0,
    )
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data[EVENT_DATA_NAME] == button.name
    assert events[0].data[EVENT_DATA_ADDRESS] == "80:e4:da:78:6e:11"
    assert events[0].data[EVENT_DATA_TYPE] == CLICK_TYPE_SINGLE
    assert events[0].data[EVENT_DATA_QUEUED_TIME] == 0


async def test_button_click_event_ignored(hass: HomeAssistant) -> None:
    """Test that ignored click types don't fire events."""
    flic_client = MockFlicClient()
    events: list = []

    def capture_event(event):
        events.append(event)

    hass.bus.async_listen(EVENT_NAME, capture_event)

    button = FlicButton(hass, flic_client, "80:e4:da:78:6e:11", 3, [CLICK_TYPE_SINGLE])

    button._on_click(
        MagicMock(),
        MockClickType.ButtonSingleClick,
        False,
        0,
    )
    await hass.async_block_till_done()

    assert len(events) == 0


async def test_button_queued_event_dropped(hass: HomeAssistant) -> None:
    """Test that queued events beyond timeout are dropped."""
    flic_client = MockFlicClient()
    events: list = []

    def capture_event(event):
        events.append(event)

    hass.bus.async_listen(EVENT_NAME, capture_event)

    button = FlicButton(hass, flic_client, "80:e4:da:78:6e:11", 3, None)

    button._on_click(
        MagicMock(),
        MockClickType.ButtonSingleClick,
        True,
        5,
    )
    await hass.async_block_till_done()

    assert len(events) == 0


async def test_button_up_down_state_change(hass: HomeAssistant) -> None:
    """Test button state changes on up/down events."""
    flic_client = MockFlicClient()

    button = FlicButton(hass, flic_client, "80:e4:da:78:6e:11", 3, None)
    button.hass = hass
    button.entity_id = "binary_sensor.flic_80e4da786e11"

    assert button.is_on is True

    button._on_up_down(MagicMock(), MockClickType.ButtonDown, False, 0)
    assert button.is_on is False

    button._on_up_down(MagicMock(), MockClickType.ButtonUp, False, 0)
    assert button.is_on is True


async def test_button_restore_channel(hass: HomeAssistant) -> None:
    """Test button channel restoration."""
    flic_client = MockFlicClient()
    new_flic_client = MockFlicClient()

    button = FlicButton(hass, flic_client, "80:e4:da:78:6e:11", 3, None)

    old_channel = button._channel
    button.restore_channel(new_flic_client)

    assert button._channel is not old_channel
    assert len(new_flic_client.channels) == 1


async def test_force_disconnect_shuts_down_socket(hass: HomeAssistant) -> None:
    """Test that force_disconnect shuts down the client socket."""
    flic_client = MockFlicClient()
    mock_socket = MagicMock()
    flic_client._sock = mock_socket

    add_entities_mock = MagicMock()
    config = {
        CONF_HOST: "localhost",
        CONF_PORT: 5551,
        CONF_DISCOVERY: False,
        CONF_TIMEOUT: 3,
    }

    manager = FlicConnectionManager(hass, "localhost", 5551, config, add_entities_mock)
    manager._client = flic_client

    manager._force_disconnect()

    mock_socket.shutdown.assert_called_once_with(socket.SHUT_RDWR)


async def test_shutdown_stops_manager(hass: HomeAssistant) -> None:
    """Test that shutdown flag is checked in run loop."""
    add_entities_mock = MagicMock()
    config = {
        CONF_HOST: "localhost",
        CONF_PORT: 5551,
        CONF_DISCOVERY: False,
        CONF_TIMEOUT: 3,
    }

    manager = FlicConnectionManager(hass, "localhost", 5551, config, add_entities_mock)
    manager._shutdown = True

    assert manager._shutdown is True


async def test_connection_status_changed_logging(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test connection status change logging."""
    flic_client = MockFlicClient()

    button = FlicButton(hass, flic_client, "80:e4:da:78:6e:11", 3, None)

    button._on_connection_status_changed(
        MagicMock(),
        MockConnectionStatus.Disconnected,
        MockDisconnectReason.Unspecified,
    )

    assert "disconnected" in caplog.text.lower()

    caplog.clear()

    button._on_connection_status_changed(
        MagicMock(),
        MockConnectionStatus.Ready,
        MockDisconnectReason.Unspecified,
    )

    assert "ready" in caplog.text.lower()


async def test_scan_wizard_restart_on_completion(hass: HomeAssistant) -> None:
    """Test scan wizard restarts after completion."""
    flic_client = MockFlicClient()
    add_entities_mock = MagicMock()
    config = {
        CONF_HOST: "localhost",
        CONF_PORT: 5551,
        CONF_DISCOVERY: True,
        CONF_TIMEOUT: 3,
    }

    scan_wizard_count = [0]
    original_scan_wizard = MockScanWizard

    def counting_scan_wizard():
        scan_wizard_count[0] += 1
        return original_scan_wizard()

    mock_pyflic.ScanWizard = counting_scan_wizard

    manager = FlicConnectionManager(hass, "localhost", 5551, config, add_entities_mock)
    manager._client = flic_client

    manager._start_scanning()

    assert scan_wizard_count[0] == 1

    wizard = flic_client.scan_wizard
    assert wizard is not None
    wizard.on_completed(
        wizard,
        MockScanWizardResult.WizardSuccess,
        "80:e4:da:78:6e:11",
        "Flic Button",
    )

    assert scan_wizard_count[0] == 2

    mock_pyflic.ScanWizard = original_scan_wizard


async def test_ignored_click_types_channel_setup(hass: HomeAssistant) -> None:
    """Test channel setup with different ignored click types."""
    flic_client = MockFlicClient()

    button_all_ignored = FlicButton(
        hass,
        flic_client,
        "80:e4:da:78:6e:11",
        3,
        [CLICK_TYPE_SINGLE, CLICK_TYPE_DOUBLE, CLICK_TYPE_HOLD],
    )
    assert button_all_ignored._channel is not None
    assert button_all_ignored._channel.on_button_click_or_hold is None

    button_double_ignored = FlicButton(
        hass,
        flic_client,
        "80:e4:da:78:6e:12",
        3,
        [CLICK_TYPE_DOUBLE],
    )
    assert button_double_ignored._channel.on_button_click_or_hold is not None

    button_hold_ignored = FlicButton(
        hass,
        flic_client,
        "80:e4:da:78:6e:13",
        3,
        [CLICK_TYPE_HOLD],
    )
    assert button_hold_ignored._channel.on_button_single_or_double_click is not None


async def test_on_pong_sets_event(hass: HomeAssistant) -> None:
    """Test that _on_pong sets the pong_received event."""
    add_entities_mock = MagicMock()
    config = {
        CONF_HOST: "localhost",
        CONF_PORT: 5551,
        CONF_DISCOVERY: False,
        CONF_TIMEOUT: 3,
    }

    manager = FlicConnectionManager(hass, "localhost", 5551, config, add_entities_mock)
    assert not manager._pong_received.is_set()

    manager._on_pong({})

    assert manager._pong_received.is_set()


async def test_wait_for_pong_success(hass: HomeAssistant) -> None:
    """Test _wait_for_pong when pong is received in time."""
    add_entities_mock = MagicMock()
    config = {
        CONF_HOST: "localhost",
        CONF_PORT: 5551,
        CONF_DISCOVERY: False,
        CONF_TIMEOUT: 3,
    }

    manager = FlicConnectionManager(hass, "localhost", 5551, config, add_entities_mock)
    manager._connected = True
    manager._pong_received.set()

    manager._wait_for_pong()


async def test_wait_for_pong_timeout_forces_disconnect(hass: HomeAssistant) -> None:
    """Test _wait_for_pong forces disconnect on timeout."""
    flic_client = MockFlicClient()
    mock_socket = MagicMock()
    flic_client._sock = mock_socket

    add_entities_mock = MagicMock()
    config = {
        CONF_HOST: "localhost",
        CONF_PORT: 5551,
        CONF_DISCOVERY: False,
        CONF_TIMEOUT: 3,
    }

    manager = FlicConnectionManager(hass, "localhost", 5551, config, add_entities_mock)
    manager._client = flic_client
    manager._connected = True
    manager._pong_received.clear()

    with patch(
        "homeassistant.components.flic.binary_sensor.PONG_TIMEOUT_SECONDS", 0.01
    ):
        manager._wait_for_pong()

    mock_socket.shutdown.assert_called_once_with(socket.SHUT_RDWR)


async def test_wait_for_pong_ignores_timeout_when_disconnected(
    hass: HomeAssistant,
) -> None:
    """Test _wait_for_pong ignores timeout if already disconnected."""
    add_entities_mock = MagicMock()
    config = {
        CONF_HOST: "localhost",
        CONF_PORT: 5551,
        CONF_DISCOVERY: False,
        CONF_TIMEOUT: 3,
    }

    manager = FlicConnectionManager(hass, "localhost", 5551, config, add_entities_mock)
    manager._connected = False
    manager._pong_received.clear()

    with patch(
        "homeassistant.components.flic.binary_sensor.PONG_TIMEOUT_SECONDS", 0.01
    ):
        manager._wait_for_pong()


async def test_setup_client_registers_callbacks(hass: HomeAssistant) -> None:
    """Test _setup_client registers necessary callbacks."""
    flic_client = MockFlicClient()
    flic_client.addresses = ("80:e4:da:78:6e:11",)
    entities_added: list = []

    def capture_entities(entities: list) -> None:
        entities_added.extend(entities)

    config = {
        CONF_HOST: "localhost",
        CONF_PORT: 5551,
        CONF_DISCOVERY: False,
        CONF_TIMEOUT: 3,
    }

    mock_pyflic.FlicClient = MockFlicClient

    manager = FlicConnectionManager(hass, "localhost", 5551, config, capture_entities)
    manager._client = flic_client

    manager._setup_client()

    assert flic_client.on_new_verified_button is not None
    assert len(entities_added) == 1


async def test_reconnect_logging_tiers(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that reconnect logging reduces frequency over time."""
    add_entities_mock = MagicMock()
    config = {
        CONF_HOST: "localhost",
        CONF_PORT: 5551,
        CONF_DISCOVERY: False,
        CONF_TIMEOUT: 3,
    }

    manager = FlicConnectionManager(hass, "localhost", 5551, config, add_entities_mock)

    caplog.clear()
    manager._reconnect_attempts = 12
    manager._log_reconnect_attempt()
    assert "attempt 12" in caplog.text
    assert "now logging" not in caplog.text

    caplog.clear()
    manager._reconnect_attempts = 13
    manager._log_reconnect_attempt()
    assert "attempt 13" in caplog.text
    assert "now logging hourly" in caplog.text

    caplog.clear()
    manager._reconnect_attempts = 24
    manager._log_reconnect_attempt()
    assert "attempt 24" in caplog.text
    assert "logging once per hour" in caplog.text

    caplog.clear()
    manager._reconnect_attempts = 15
    manager._log_reconnect_attempt()
    assert caplog.text == ""

    caplog.clear()
    manager._reconnect_attempts = 289
    manager._log_reconnect_attempt()
    assert "attempt 289" in caplog.text
    assert "now logging daily" in caplog.text

    caplog.clear()
    manager._reconnect_attempts = 576
    manager._log_reconnect_attempt()
    assert "attempt 576" in caplog.text
    assert "logging once per day" in caplog.text

    caplog.clear()
    manager._reconnect_attempts = 300
    manager._log_reconnect_attempt()
    assert caplog.text == ""
