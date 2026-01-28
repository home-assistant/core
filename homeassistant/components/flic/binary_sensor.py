"""Support to use flic buttons as a binary sensor."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from datetime import timedelta
import logging
import socket
import threading
import time

import pyflic
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.const import (
    CONF_DISCOVERY,
    CONF_HOST,
    CONF_PORT,
    CONF_TIMEOUT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 3

CLICK_TYPE_SINGLE = "single"
CLICK_TYPE_DOUBLE = "double"
CLICK_TYPE_HOLD = "hold"
CLICK_TYPES = [CLICK_TYPE_SINGLE, CLICK_TYPE_DOUBLE, CLICK_TYPE_HOLD]

CONF_IGNORED_CLICK_TYPES = "ignored_click_types"

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5551

EVENT_NAME = "flic_click"
EVENT_DATA_NAME = "button_name"
EVENT_DATA_ADDRESS = "button_address"
EVENT_DATA_TYPE = "click_type"
EVENT_DATA_QUEUED_TIME = "queued_time"

PING_INTERVAL = timedelta(seconds=10)
PONG_TIMEOUT_SECONDS = 5
RECONNECT_BACKOFF_BASE = 1
RECONNECT_BACKOFF_MAX = 300

PLATFORM_SCHEMA = BINARY_SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_DISCOVERY, default=True): cv.boolean,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_IGNORED_CLICK_TYPES): vol.All(
            cv.ensure_list, [vol.In(CLICK_TYPES)]
        ),
    }
)


class FlicConnectionManager(threading.Thread):
    """Manage flicd connection with automatic reconnection.

    Runs as a dedicated thread that monitors the pyflic event loop.
    Uses periodic pings to detect stale connections. When the connection
    is lost, automatically attempts to reconnect with exponential backoff.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        config: ConfigType,
        add_entities: AddEntitiesCallback,
    ) -> None:
        """Initialize the connection manager."""
        super().__init__(daemon=True)
        self._hass = hass
        self._host = host
        self._port = port
        self._config = config
        self._add_entities = add_entities
        self._client: pyflic.FlicClient | None = None
        self._buttons: list[FlicButton] = []
        self._known_addresses: set[str] = set()
        self._shutdown = False
        self._reconnect_attempts = 0
        self._lock = threading.Lock()
        self._connected = False
        self._pong_received = threading.Event()
        self._cancel_ping: Callable[[], None] | None = None

    def _connect(self) -> bool:
        """Attempt to connect to flicd."""
        try:
            self._client = pyflic.FlicClient(self._host, self._port)
        except (ConnectionRefusedError, OSError, TimeoutError) as ex:
            _LOGGER.debug("Failed to connect to flicd: %s", ex)
            return False
        return True

    def _on_pong(self, info: dict) -> None:
        """Handle pong response from flicd."""
        self._pong_received.set()

    def _force_disconnect(self) -> None:
        """Force disconnect by shutting down socket for reading.

        This causes recv() to return 0, making handle_events() exit cleanly.
        Works even when called from another thread on a dead connection.
        """
        with self._lock:
            if self._client is None:
                return
            with suppress(OSError):
                # Access private _sock because pyflic doesn't expose the socket
                # SHUT_RDWR sends FIN to server so flicd knows to clean up
                self._client._sock.shutdown(socket.SHUT_RDWR)  # noqa: SLF001

    def _setup_client(self) -> None:
        """Set up callbacks and channels on the client."""
        if self._client is None:
            return

        def new_button_callback(address: str) -> None:
            """Set up newly verified button as device in Home Assistant."""
            self._setup_button(address)

        self._client.on_new_verified_button = new_button_callback

        if self._config.get(CONF_DISCOVERY):
            self._start_scanning()

        def get_info_callback(items: dict) -> None:
            """Add entities for already verified buttons."""
            addresses = items.get("bd_addr_of_verified_buttons") or []
            for address in addresses:
                self._setup_button(address)

        self._client.get_info(get_info_callback)

    def _setup_button(self, address: str) -> None:
        """Set up a single button device."""
        with self._lock:
            if address in self._known_addresses:
                return
            self._known_addresses.add(address)

        if self._client is None:
            return

        timeout: int = self._config[CONF_TIMEOUT]
        ignored_click_types: list[str] | None = self._config.get(
            CONF_IGNORED_CLICK_TYPES
        )
        button = FlicButton(
            self._hass, self._client, address, timeout, ignored_click_types
        )
        _LOGGER.debug("Connected to button %s", address)

        with self._lock:
            self._buttons.append(button)

        self._add_entities([button])

    def _restore_buttons(self) -> None:
        """Re-add button channels after reconnection."""
        if self._client is None:
            return

        with self._lock:
            for button in self._buttons:
                button.restore_channel(self._client)
                _LOGGER.debug("Restored button channel: %s", button.address)

    def _start_scanning(self) -> None:
        """Start a new flic client for scanning and connecting to new buttons."""
        if self._client is None:
            return

        scan_wizard = pyflic.ScanWizard()

        def scan_completed_callback(
            wizard: pyflic.ScanWizard,
            result: pyflic.ScanWizardResult,
            address: str,
            name: str,
        ) -> None:
            """Restart scan wizard to constantly check for new buttons."""
            if result == pyflic.ScanWizardResult.WizardSuccess:
                _LOGGER.debug("Found new button %s", address)
            elif result != pyflic.ScanWizardResult.WizardFailedTimeout:
                _LOGGER.warning(
                    "Failed to connect to button %s. Reason: %s", address, result
                )

            if not self._shutdown:
                self._start_scanning()

        scan_wizard.on_completed = scan_completed_callback
        self._client.add_scan_wizard(scan_wizard)

    def _start_ping_monitor(self) -> None:
        """Start periodic ping health checks."""

        @callback
        def async_ping(now: object) -> None:
            """Send ping to check connection health."""
            if not self._connected or self._shutdown or self._client is None:
                return

            self._pong_received.clear()

            try:
                self._client.get_info(self._on_pong)
            except (OSError, AttributeError):
                _LOGGER.debug("Failed to send ping, connection may be dead")
                return

            self._hass.async_add_executor_job(self._wait_for_pong)

        self._cancel_ping = async_track_time_interval(
            self._hass,
            async_ping,
            PING_INTERVAL,
            cancel_on_shutdown=True,
        )

    def _wait_for_pong(self) -> None:
        """Wait for pong response, force disconnect on timeout."""
        if self._pong_received.wait(timeout=PONG_TIMEOUT_SECONDS):
            _LOGGER.debug("Ping successful")
            return

        if not self._connected:
            _LOGGER.debug("Ping timeout ignored, already disconnected")
            return

        _LOGGER.warning("Ping timeout, connection is stale, forcing disconnect")
        self._force_disconnect()

    def _log_reconnect_attempt(self) -> None:
        """Log reconnect attempt with tiered frequency to avoid spam.

        Logging frequency reduces over time:
        - First 12 attempts (~30 min): every attempt
        - Attempts 13-288: every 12 attempts (~1 hour)
        - After 288: every 288 attempts (~24 hours)
        """
        attempt = self._reconnect_attempts

        should_log = False
        log_note = ""

        if attempt <= 12:
            should_log = True
        elif attempt == 13:
            should_log = True
            log_note = " (now logging hourly, still retrying every 5 minutes)"
        elif attempt <= 288 and attempt % 12 == 0:
            should_log = True
            log_note = " (logging once per hour, still retrying every 5 minutes)"
        elif attempt == 289:
            should_log = True
            log_note = " (now logging daily, still retrying every 5 minutes)"
        elif attempt % 288 == 0:
            should_log = True
            log_note = " (logging once per day, still retrying every 5 minutes)"

        if should_log:
            _LOGGER.info(
                "Attempting to reconnect to flicd (attempt %d)%s",
                attempt,
                log_note,
            )

    def _backoff_sleep(self) -> None:
        """Sleep with exponential backoff before next reconnect attempt."""
        backoff = min(
            RECONNECT_BACKOFF_BASE * (2 ** (self._reconnect_attempts - 1)),
            RECONNECT_BACKOFF_MAX,
        )
        time.sleep(backoff)

    def run(self) -> None:
        """Thread run loop with automatic reconnection."""

        @callback
        def register_shutdown() -> None:
            """Register shutdown handler."""

            def shutdown(event: object) -> None:
                """Shutdown the thread."""
                _LOGGER.debug("Signaled to shutdown flic connection manager")
                self._shutdown = True
                self._force_disconnect()

            self._hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)

        self._hass.add_job(register_shutdown)
        self._hass.add_job(self._start_ping_monitor)

        while not self._shutdown:
            if self._client is None:
                if self._reconnect_attempts > 0:
                    self._log_reconnect_attempt()

                if not self._connect():
                    self._reconnect_attempts += 1
                    self._backoff_sleep()
                    continue

                _LOGGER.info("Connected to flicd at %s:%s", self._host, self._port)
                self._reconnect_attempts = 0

                if self._buttons:
                    self._restore_buttons()
                else:
                    self._setup_client()

            self._connected = True
            assert self._client is not None

            try:
                self._client.handle_events()
            except OSError as ex:
                _LOGGER.debug("flicd event loop ended: %s", ex)

            self._connected = False

            if not self._shutdown:
                _LOGGER.warning("Connection to flicd lost")
                self._client = None
                self._reconnect_attempts = 1

        _LOGGER.debug("Flic connection manager shutdown complete")


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the flic platform."""
    host: str = config[CONF_HOST]
    port: int = config[CONF_PORT]

    manager = FlicConnectionManager(hass, host, port, config, add_entities)
    manager.start()


class FlicButton(BinarySensorEntity):
    """Representation of a flic button."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        client: pyflic.FlicClient,
        address: str,
        timeout: int,
        ignored_click_types: list[str] | None,
    ) -> None:
        """Initialize the flic button."""
        self._attr_extra_state_attributes = {"address": address}
        self._attr_name = f"flic_{address.replace(':', '')}"
        self._attr_unique_id = format_mac(address)
        self._hass = hass
        self._address = address
        self._timeout = timeout
        self._attr_is_on = True
        self._ignored_click_types = ignored_click_types or []
        self._hass_click_types = {
            pyflic.ClickType.ButtonClick: CLICK_TYPE_SINGLE,
            pyflic.ClickType.ButtonSingleClick: CLICK_TYPE_SINGLE,
            pyflic.ClickType.ButtonDoubleClick: CLICK_TYPE_DOUBLE,
            pyflic.ClickType.ButtonHold: CLICK_TYPE_HOLD,
        }

        self._channel = self._create_channel()
        client.add_connection_channel(self._channel)

    @property
    def address(self) -> str:
        """Return the button address."""
        return self._address

    def restore_channel(self, client: pyflic.FlicClient) -> None:
        """Restore the connection channel after reconnection."""
        self._channel = self._create_channel()
        client.add_connection_channel(self._channel)

    def _create_channel(self) -> pyflic.ButtonConnectionChannel:
        """Create a new connection channel to the button."""
        channel = pyflic.ButtonConnectionChannel(self._address)
        channel.on_button_up_or_down = self._on_up_down
        channel.on_connection_status_changed = self._on_connection_status_changed

        if set(self._ignored_click_types) == set(CLICK_TYPES):
            return channel

        if CLICK_TYPE_DOUBLE in self._ignored_click_types:
            channel.on_button_click_or_hold = self._on_click
        elif CLICK_TYPE_HOLD in self._ignored_click_types:
            channel.on_button_single_or_double_click = self._on_click
        else:
            channel.on_button_single_or_double_click_or_hold = self._on_click

        return channel

    def _queued_event_check(self, click_type: pyflic.ClickType, time_diff: int) -> bool:
        """Generate a log message and returns true if timeout exceeded."""
        time_string = f"{time_diff:d} {'second' if time_diff == 1 else 'seconds'}"

        if time_diff > self._timeout:
            _LOGGER.warning(
                "Queued %s dropped for %s. Time in queue was %s",
                click_type,
                self._address,
                time_string,
            )
            return True
        _LOGGER.debug(
            "Queued %s allowed for %s. Time in queue was %s",
            click_type,
            self._address,
            time_string,
        )
        return False

    def _on_up_down(
        self,
        channel: pyflic.ButtonConnectionChannel,
        click_type: pyflic.ClickType,
        was_queued: bool,
        time_diff: int,
    ) -> None:
        """Update device state, if event was not queued."""
        if was_queued and self._queued_event_check(click_type, time_diff):
            return

        self._attr_is_on = click_type != pyflic.ClickType.ButtonDown
        self.schedule_update_ha_state()

    def _on_click(
        self,
        channel: pyflic.ButtonConnectionChannel,
        click_type: pyflic.ClickType,
        was_queued: bool,
        time_diff: int,
    ) -> None:
        """Fire click event, if event was not queued."""
        if was_queued and self._queued_event_check(click_type, time_diff):
            return

        hass_click_type = self._hass_click_types[click_type]
        if hass_click_type in self._ignored_click_types:
            return

        self._hass.bus.fire(
            EVENT_NAME,
            {
                EVENT_DATA_NAME: self.name,
                EVENT_DATA_ADDRESS: self._address,
                EVENT_DATA_QUEUED_TIME: time_diff,
                EVENT_DATA_TYPE: hass_click_type,
            },
        )

    def _on_connection_status_changed(
        self,
        channel: pyflic.ButtonConnectionChannel,
        connection_status: pyflic.ConnectionStatus,
        disconnect_reason: pyflic.DisconnectReason,
    ) -> None:
        """Handle button connection status changes."""
        if connection_status == pyflic.ConnectionStatus.Disconnected:
            _LOGGER.warning(
                "Button (%s) disconnected. Reason: %s",
                self._address,
                disconnect_reason,
            )
        elif connection_status == pyflic.ConnectionStatus.Ready:
            _LOGGER.info("Button (%s) connected and ready", self._address)
