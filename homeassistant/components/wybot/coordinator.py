"""DataUpdateCoordinator for the WyBot integration."""

import asyncio
from datetime import datetime, timedelta
import logging
import time
from typing import Any, override

from wybot import WybotAuthError, WyBotBLEClient, WyBotHTTPClient, WyBotMQTTClient
from wybot.dp_models import GenericDP
from wybot.models import Command, Device, Docker, Group

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .bluetooth_adapter import HomeAssistantBluetoothAdapter
from .const import BLE_MAX_CONSECUTIVE_FAILURES, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Consecutive failed update cycles before the integration is marked not-ready.
# pywybot itself retries each HTTP request with backoff, so this counts whole
# cycles, not individual attempts.
MAX_HTTP_RETRIES = 3

# Overall update timeout — safety net; individual operations have their own timeouts
UPDATE_TIMEOUT = 120

# BLE failure recovery — re-enable BLE after this many seconds
BLE_RECOVERY_SECONDS = 300  # 5 minutes

# Mark the integration unavailable when no transport (BLE, MQTT, or the HTTP
# keepalive) has succeeded within this window. Longer than the HTTP keepalive
# interval (60s) so a couple of missed cycles do not cause flapping.
AVAILABILITY_TIMEOUT = timedelta(minutes=3)


class WyBotCoordinator(DataUpdateCoordinator):
    """Coordinates data between WyBot and Home Assistant.

    Architecture: BLE-primary with MQTT fallback
    - BLE polling is attempted first for all devices in range
    - MQTT is used only when BLE fails or device is out of range
    - HTTP session refresh keeps MQTT session alive for fallback
    """

    wybot_http_client: WyBotHTTPClient
    wybot_mqtt_client: WyBotMQTTClient
    wybot_ble_client: WyBotBLEClient
    hass: HomeAssistant
    data: dict[str, Group]
    initial_load: bool = False
    _connection_available: bool = True
    _http_failure_count: int = 0
    _mqtt_failure_count: int = 0
    _last_status_query_time: float = 0.0
    _last_http_refresh_time: float = 0.0
    _online_devices: set[str] = set()
    _initial_query_start_time: float = 0.0

    # BLE command tracking
    _ble_command_enabled: bool = True
    _ble_command_failures: dict[str, int]  # device_id -> consecutive failure count
    _ble_disabled_at: dict[str, float]  # device_id -> time.time() when BLE was disabled

    # Track last MQTT data received
    _last_mqtt_data: dict[str, datetime]  # device_id -> last MQTT data time

    # Track last BLE poll time
    _last_ble_poll: dict[str, datetime]  # device_id -> last BLE poll time

    # Track data source per device (for diagnostics and logging)
    _data_source: dict[str, str]  # device_id -> "ble" | "mqtt"

    # Track BLE availability per device
    _ble_available: dict[str, bool]  # device_id -> last BLE poll succeeded

    # MQTT lazy connection state
    _mqtt_connected: bool = False
    # Time of the most recent successful MQTT (re)connect (diagnostic)
    _mqtt_last_connected_at: datetime | None = None

    # Time of the most recent successful HTTP contact with the WyBot cloud
    _last_http_success: datetime | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        wybot_http_client: WyBotHTTPClient,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="WyBot Coordinator",
            update_interval=timedelta(seconds=30),
        )
        self.wybot_http_client = wybot_http_client
        self.wybot_mqtt_client = WyBotMQTTClient(self.on_message)
        # DON'T connect MQTT here - use lazy connection when needed as fallback
        self.wybot_ble_client = WyBotBLEClient(HomeAssistantBluetoothAdapter(hass))
        self.data = {}

        # Initialize data tracking
        self._last_mqtt_data = {}
        self._last_ble_poll = {}
        self._data_source = {}
        self._ble_available = {}

        # Initialize BLE command tracking
        self._ble_command_failures = {}
        self._ble_disabled_at = {}
        self._online_devices = set()

    async def async_stop(self) -> None:
        """Stop the MQTT client.

        Always disconnect: pywybot's connect() starts a background reconnect
        task, and a later subscription error can clear _mqtt_connected while
        that task keeps running, so gating disconnect on the flag would leak it.
        """
        _LOGGER.info("Stopping MQTT client")
        await self.wybot_mqtt_client.disconnect()
        self._mqtt_connected = False

    async def _ensure_mqtt_connected(self) -> bool:
        """Lazy connect to MQTT (only when needed as fallback).

        Self-healing: if our flag claims connected but the client disagrees,
        reset and reconnect. This catches silent drops where the disconnect
        callback didn't fire or aiomqtt's auto-retry is wedged.

        Returns:
            True if MQTT is connected, False otherwise
        """
        if self._mqtt_connected:
            if self.wybot_mqtt_client.is_connected():
                return True
            _LOGGER.warning(
                "MQTT state drift detected: flag says connected, client says no; reconnecting"
            )
            self._mqtt_connected = False

        _LOGGER.info("Connecting to MQTT (fallback mode)")
        try:
            # connect() waits for the link to actually come up and reports the
            # result, so we never mark ourselves connected before publishes can
            # be delivered.
            if not await self.wybot_mqtt_client.connect():
                _LOGGER.warning("MQTT connection did not come up in time")
                self._mqtt_connected = False
                return False
            self._mqtt_connected = True
            self._mqtt_last_connected_at = dt_util.utcnow()
            # Subscribe to topics for all known devices
            if self.data:
                await self.subscribe_mqtt(self.data)
        except Exception as err:  # noqa: BLE001
            # Transport failures must not crash the coordinator; MQTT is a
            # fallback layer, so degrade gracefully and retry next cycle.
            _LOGGER.warning("MQTT connection failed: %s", err)
            self._mqtt_connected = False
            return False
        _LOGGER.info("MQTT connected successfully (fallback ready)")
        return True

    def _record_mqtt_data_received(self, device_id: str) -> None:
        """Record that MQTT data was received from a device.

        Marks data_source="mqtt" only when a real MQTT message arrives, so
        the diagnostic sensor doesn't flap on every poll cycle that *tried*
        MQTT fallback.

        Args:
            device_id: The device ID that sent data
        """
        self._last_mqtt_data[device_id] = dt_util.utcnow()
        self._data_source[device_id] = "mqtt"
        _LOGGER.debug("Recorded MQTT data received from device %s", device_id)

    @property
    def mqtt_connected(self) -> bool:
        """Return whether the MQTT fallback is currently connected."""
        return self._mqtt_connected

    @property
    def mqtt_last_connected_at(self) -> datetime | None:
        """Return the time of the most recent successful MQTT connect."""
        return self._mqtt_last_connected_at

    def get_last_ble_communication(self, device_id: str) -> datetime | None:
        """Get the last successful BLE communication time for a device.

        Args:
            device_id: The device ID to query

        Returns:
            datetime of last BLE communication, or None if never communicated via BLE
        """
        return self._last_ble_poll.get(device_id)

    def get_last_mqtt_communication(self, device_id: str) -> datetime | None:
        """Get the last MQTT data received time for a device.

        Args:
            device_id: The device ID to query

        Returns:
            datetime of last MQTT data, or None if never received MQTT data
        """
        return self._last_mqtt_data.get(device_id)

    def get_data_source(self, device_id: str) -> str | None:
        """Get the current data source for a device.

        Args:
            device_id: The device ID to query

        Returns:
            "ble" or "mqtt" depending on last successful poll, or None if unknown
        """
        return self._data_source.get(device_id)

    def is_ble_available(self, device_id: str) -> bool | None:
        """Check if BLE is available for a device.

        Args:
            device_id: The device ID to query

        Returns:
            True if last BLE poll succeeded, False if failed, None if never tried
        """
        return self._ble_available.get(device_id)

    def _get_device_ble_info(self, group: Group) -> tuple[str | None, str | None]:
        """Get the BLE name and device ID for a group.

        Prefers docker BLE name since dock relays to robot.

        Args:
            group: The device group

        Returns:
            Tuple of (ble_name, device_id) or (None, None) if no BLE available
        """
        if group.docker and group.docker.ble_name:
            return group.docker.ble_name, group.docker.docker_id
        if group.device and group.device.ble_name:
            return group.device.ble_name, group.device.device_id
        return None, None

    @staticmethod
    def _mqtt_query_ids(group: Group) -> list[str]:
        """Return the device IDs to query over MQTT for a group.

        The robot and dock publish their DPs on separate MQTT topics, so both
        must be queried on fallback: robot entities/vacuum consume the robot's
        DPs while the dock sensors consume the dock's.
        """
        ids: list[str] = []
        if group.device:
            ids.append(group.device.device_id)
        if group.docker:
            ids.append(group.docker.docker_id)
        return ids

    def _update_device_dps_from_ble(
        self, group: Group, device_id: str, dps: list[dict[str, Any]]
    ) -> None:
        """Update device DPs from BLE response.

        Args:
            group: The device group to update
            device_id: The device ID
            dps: List of DP dicts from BLE response
        """
        if not dps:
            return

        # Create a command-like structure to reuse existing DP processing
        cmd_data: dict[str, Any] = {"cmd": 5, "ts": 0, "dp": dps}
        command = Command(**cmd_data)
        dp_dict: dict[str, Any] = command.get_dps_as_keyed_dict()

        if group.docker and group.docker.docker_id == device_id:
            group.docker.dps = {**group.docker.dps, **dp_dict}
            _LOGGER.debug(
                "Updated docker %s DPs from BLE: %s",
                device_id,
                list(dp_dict.keys()),
            )
        elif group.device:
            group.device.dps = {**group.device.dps, **dp_dict}
            _LOGGER.debug(
                "Updated device %s DPs from BLE: %s",
                device_id,
                list(dp_dict.keys()),
            )

    def _maybe_recover_ble(self, device_id: str) -> None:
        """Re-enable BLE for a device if enough time has passed since it was disabled."""
        disabled_at = self._ble_disabled_at.get(device_id)
        if (
            disabled_at is not None
            and (time.time() - disabled_at) >= BLE_RECOVERY_SECONDS
        ):
            _LOGGER.info(
                "Re-enabling BLE for device %s after %ds recovery period",
                device_id,
                BLE_RECOVERY_SECONDS,
            )
            self._ble_command_failures.pop(device_id, None)
            self._ble_disabled_at.pop(device_id, None)

    async def _poll_all_devices_via_ble(self) -> list[str]:
        """Poll all devices via BLE (primary data source).

        BLE provides faster, more reliable local communication when the device
        is in range. This is the PRIMARY data source in the BLE-first architecture.

        Returns:
            List of device IDs that need MQTT fallback (failed BLE or no BLE name)
        """
        devices_needing_mqtt: list[str] = []
        now = dt_util.utcnow()

        for group_id, group in self.data.items():
            ble_name, device_id = self._get_device_ble_info(group)

            if not ble_name or not device_id:
                # No BLE name available, will need MQTT
                devices_needing_mqtt.extend(self._mqtt_query_ids(group))
                continue

            # Check if BLE should be recovered for this device
            self._maybe_recover_ble(device_id)

            _LOGGER.debug(
                "BLE polling device %s via %s (primary)",
                device_id,
                ble_name,
            )

            try:
                dps = await self.wybot_ble_client.query_status(ble_name)

                if dps:
                    _LOGGER.debug(
                        "BLE poll success for %s: %d DPs received",
                        device_id,
                        len(dps),
                    )
                    self._update_device_dps_from_ble(group, device_id, dps)
                    self.data[group_id] = group

                    # Track successful BLE poll
                    self._last_ble_poll[device_id] = now
                    self._data_source[device_id] = "ble"
                    self._ble_available[device_id] = True
                else:
                    # BLE returned no data, need MQTT fallback
                    _LOGGER.debug(
                        "BLE poll for %s returned no data, using MQTT fallback",
                        device_id,
                    )
                    devices_needing_mqtt.extend(self._mqtt_query_ids(group))
                    self._ble_available[device_id] = False

            except Exception as err:  # noqa: BLE001
                _LOGGER.debug(
                    "BLE poll failed for %s: %s, using MQTT fallback",
                    device_id,
                    err,
                )
                devices_needing_mqtt.extend(self._mqtt_query_ids(group))
                self._ble_available[device_id] = False

        return devices_needing_mqtt

    async def _poll_devices_via_mqtt(self, device_ids: list[str]) -> None:
        """Poll specific devices via MQTT (fallback).

        Only called when BLE fails or device is out of range.

        Args:
            device_ids: List of device IDs that need MQTT polling
        """
        if not device_ids:
            return

        # Ensure MQTT is connected (lazy connection)
        if not await self._ensure_mqtt_connected():
            _LOGGER.warning(
                "MQTT fallback unavailable for %d devices",
                len(device_ids),
            )
            return

        _LOGGER.debug(
            "Using MQTT fallback for %d devices: %s",
            len(device_ids),
            device_ids,
        )

        for device_id in device_ids:
            await self.wybot_mqtt_client.ensure_device_sends_statuses(device_id)
            self._last_status_query_time = time.time()

    async def _maybe_refresh_http_session(self) -> None:
        """Periodically refresh HTTP session to keep MQTT fallback ready.

        The WyBot cloud may only relay MQTT data for "active" users,
        so we need to periodically refresh the HTTP session.
        """
        current_time = time.time()
        # Refresh every 60 seconds
        if current_time - self._last_http_refresh_time < 60.0:
            return

        _LOGGER.debug("Refreshing HTTP session to keep MQTT fallback ready")
        try:
            await self.wybot_http_client.register_presence()
            fresh = await self.wybot_http_client.get_indexed_current_grouped_devices()
            # Apply the response instead of discarding it: this is the only
            # post-setup device-list refresh, so it is how devices added later
            # are discovered, and it keeps _last_http_success backed by real
            # device data rather than a bare reachability ping.
            self._merge_http_groups(fresh)
            self._last_http_refresh_time = current_time
            self._last_http_success = dt_util.utcnow()
        except WybotAuthError:
            # Credentials became invalid during normal operation — let this
            # propagate so _async_update_data can trigger the reauth flow.
            raise
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("HTTP refresh failed (non-critical): %s", err)

        # MQTT keepalive: keep the fallback layer warm so silent drops are
        # detected within ~60s instead of "the next time BLE happens to fail".
        # _ensure_mqtt_connected is drift-aware and idempotent when healthy.
        if self.data:
            try:
                await self._ensure_mqtt_connected()
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("MQTT keepalive failed (non-critical): %s", err)

    def _merge_http_groups(self, fresh: dict[str, Group]) -> None:
        """Merge a cloud device-list snapshot into the coordinator data.

        Newly discovered groups are added (dynamic device discovery). For groups
        we already track, cloud DPs only fill gaps and never overwrite values a
        more recent BLE/MQTT read already populated, preserving BLE-first data.
        """
        for group_id, group in fresh.items():
            existing = self.data.get(group_id)
            if existing is None:
                self.data[group_id] = group
                continue
            if group.device is not None and existing.device is not None:
                existing.device.dps = {**group.device.dps, **existing.device.dps}
            if group.docker is not None and existing.docker is not None:
                existing.docker.dps = {**group.docker.dps, **existing.docker.dps}

    def _recently_reached(self) -> bool:
        """Return whether any transport succeeded within the availability window.

        Considers the most recent BLE poll, MQTT message, and HTTP contact. A
        full outage (all transports failing) eventually falls outside the
        window and marks the integration unavailable instead of serving stale
        cached data forever.
        """
        timestamps = [
            *self._last_ble_poll.values(),
            *self._last_mqtt_data.values(),
        ]
        if self._last_http_success is not None:
            timestamps.append(self._last_http_success)
        if not timestamps:
            return False
        return dt_util.utcnow() - max(timestamps) <= AVAILABILITY_TIMEOUT

    @override
    async def _async_update_data(self) -> dict[str, Group]:
        """Fetch data using BLE-primary with MQTT fallback architecture.

        Priority:
        1. BLE polling (primary) - for devices in Bluetooth range
        2. MQTT polling (fallback) - for devices that failed BLE
        3. HTTP session refresh - keeps MQTT fallback ready
        """
        try:
            async with asyncio.timeout(UPDATE_TIMEOUT):
                # First update: HTTP setup to get device list
                if not self.initial_load:
                    self.initial_load = True
                    _LOGGER.info("Initial load: fetching device list from HTTP API")
                    await self.wybot_http_client.register_presence()
                    await self.http_refresh_data()

                    # Log device BLE names for debugging
                    for group in self.data.values():
                        if group.device:
                            _LOGGER.info(
                                "Device %s BLE name: %s, type: %s",
                                group.device.device_id,
                                group.device.ble_name,
                                group.device.device_type,
                            )
                        if group.docker:
                            _LOGGER.info(
                                "Docker %s BLE name: %s, type: %s",
                                group.docker.docker_id,
                                group.docker.ble_name,
                                group.docker.docker_type,
                            )
                    self._initial_query_start_time = time.time()

                # BLE FIRST - try all devices via BLE (primary)
                devices_needing_mqtt = await self._poll_all_devices_via_ble()

                # MQTT FALLBACK - only for devices that failed BLE
                if devices_needing_mqtt:
                    await self._poll_devices_via_mqtt(devices_needing_mqtt)

                # Keep HTTP session active for MQTT fallback readiness
                await self._maybe_refresh_http_session()

                # Update connection availability based on whether any transport
                # actually succeeded recently — non-empty cached data alone must
                # not mask a full outage.
                if self.data and self._recently_reached():
                    self._connection_available = True
                    return self.data

                # No data from any source (or all stale) — surface as a failed
                # update so the DataUpdateCoordinator logs once now and once on
                # recovery (log-when-unavailable) and entities go unavailable.
                self._connection_available = False
                raise UpdateFailed(  # noqa: TRY301
                    translation_domain=DOMAIN, translation_key="no_data"
                )

        except (ConfigEntryAuthFailed, WybotAuthError) as err:
            # Credentials are no longer valid — trigger the reauth flow.
            self._connection_available = False
            if isinstance(err, ConfigEntryAuthFailed):
                raise
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except ConfigEntryNotReady:
            self._connection_available = False
            raise
        except UpdateFailed:
            # Already a translated update failure (e.g. no_data); preserve its
            # specific reason instead of masking it as a generic update_failed.
            self._connection_available = False
            raise
        except TimeoutError as err:
            _LOGGER.error("Timeout updating data: %s", err)
            self._connection_available = False
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="update_failed"
            ) from err
        except Exception as err:
            _LOGGER.error("Error communicating with API: %s", err)
            self._connection_available = False
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="update_failed"
            ) from err

    async def http_refresh_data(self) -> None:
        """Refresh the device list from the HTTP API.

        pywybot already retries this request with backoff internally, so this
        issues a single call and maps its typed errors onto the coordinator's
        failure modes. MQTT subscription is deferred to _ensure_mqtt_connected.
        """
        try:
            data = await self.wybot_http_client.get_indexed_current_grouped_devices()
        except WybotAuthError as err:
            _LOGGER.error("Authentication failed, credentials may be invalid")
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except Exception as err:
            self._http_failure_count += 1
            self._connection_available = False
            _LOGGER.warning("HTTP refresh failed: %s", err)
            if self._http_failure_count >= MAX_HTTP_RETRIES:
                _LOGGER.error(
                    "HTTP connection failed repeatedly, marking as unavailable"
                )
                raise ConfigEntryNotReady(
                    translation_domain=DOMAIN, translation_key="cannot_connect"
                ) from err
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="update_failed"
            ) from err

        if not data:
            self._connection_available = False
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="update_failed"
            )

        self.data = data
        self._http_failure_count = 0
        self._connection_available = True
        self._last_http_success = dt_util.utcnow()

    async def subscribe_mqtt(self, data: dict[str, Group]) -> None:
        """Subscribe to MQTT updates for a device."""
        for device in data.values():
            await self.wybot_mqtt_client.subscribe_for_device(device.device.device_id)
            if device.docker is not None:
                await self.wybot_mqtt_client.subscribe_for_device(
                    device.docker.docker_id
                )

    def on_message(self, topic: str, data: dict[str, Any]) -> None:
        """Handle a message from MQTT."""
        data_updated = False

        # pywybot forwards the raw payload (bytes) when JSON decoding fails;
        # ignore anything that is not a decoded mapping so a single malformed
        # message cannot tear down the MQTT receive loop.
        if not isinstance(data, dict):
            _LOGGER.debug("Ignoring non-mapping MQTT payload on %s", topic)
            return

        _LOGGER.debug(
            "MQTT on_message - Topic: %s, cmd: %s",
            topic,
            data.get("cmd"),
        )

        if topic.startswith("/will/"):
            device_id = topic[6:]
            is_online = data.get("online") == "1"
            _LOGGER.debug(
                "Device %s online status: %s",
                device_id,
                "online" if is_online else "offline",
            )
            # Record that we received MQTT data from this device
            self._record_mqtt_data_received(device_id)
            # Update device online status
            group = self.get_group(device_id)
            if group is not None:
                if group.device.device_id == device_id:
                    group.device.online = is_online
                elif group.docker is not None and group.docker.docker_id == device_id:
                    group.docker.online = is_online
                self.data[group.id] = group
                # Track online devices
                if is_online:
                    self._online_devices.add(device_id)
                    _LOGGER.debug("Device %s came online, querying status", device_id)
                    # on_message runs in the event loop (from the MQTT listen
                    # task) but is sync; schedule the async status query.
                    self.hass.async_create_task(
                        self.wybot_mqtt_client.ensure_device_sends_statuses(device_id)
                    )
                else:
                    self._online_devices.discard(device_id)
            # Will messages indicate device availability changes, always trigger update
            data_updated = True

        if topic.startswith("/device/DATA/send_transparent_data/"):
            device_id = topic[35:]
            # Record that we received MQTT data from this device
            self._record_mqtt_data_received(device_id)
            _LOGGER.debug(
                "Processing send_transparent_data for device %s",
                device_id,
            )
            try:
                command_response = Command(**data)
                _LOGGER.debug(
                    "Parsed Command: cmd=%s, dp_count=%s",
                    command_response.cmd,
                    len(command_response.dp),
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.error(
                    "Failed to parse Command from data: %s, error: %s", data, err
                )
                command_response = None

            if command_response is None:
                return

            group = self.get_group(device_id)
            incoming_dps: dict[str, Any] = command_response.get_dps_as_keyed_dict()
            if (
                group is not None
                and group.docker is not None
                and group.docker.docker_id == device_id
            ):
                group.docker.dps = {
                    **group.docker.dps,
                    **incoming_dps,
                }
                _LOGGER.debug(
                    "Updated docker %s DPs from send_transparent_data",
                    device_id,
                )
                data_updated = True
            elif group is not None and group.device is not None:
                group.device.dps = {
                    **group.device.dps,
                    **incoming_dps,
                }
                _LOGGER.debug(
                    "Updated device %s DPs from send_transparent_data",
                    device_id,
                )
                data_updated = True
            if group is not None:
                self.data[group.id] = group

        if topic.startswith("/device/DATA/recv_transparent_query_data/"):
            device_id = topic[41:]
            # Do NOT record device communication here: pywybot publishes our own
            # cmd=9 status queries to this same subscribed topic, so the broker
            # echoes them straight back. Counting those echoes would keep an
            # offline robot looking reachable. This branch carries no device
            # data anyway (it only logs), so genuine responses arrive as
            # send_transparent_data / recv_transparent_cmd_data instead.
            try:
                command_response = Command(**data)
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("Failed to parse query response: %s (%s)", data, err)
            else:
                _LOGGER.debug("Query CMD ---- %s ----- %s", device_id, command_response)

        if topic.startswith("/device/DATA/recv_transparent_cmd_data/"):
            device_id = topic[39:]
            # Record that we received MQTT data from this device
            self._record_mqtt_data_received(device_id)
            try:
                command_response = Command(**data)
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("Failed to parse command response: %s (%s)", data, err)
                command_response = None

            _LOGGER.debug("SEND CMD ---- %s ----- %s", device_id, command_response)

            # Update device DPs with the received data (cmd=4 contains actual values)
            group = self.get_group(device_id)
            if command_response is not None and group is not None:
                cmd_dps: dict[str, Any] = command_response.get_dps_as_keyed_dict()
                if group.docker is not None and group.docker.docker_id == device_id:
                    group.docker.dps = {
                        **group.docker.dps,
                        **cmd_dps,
                    }
                    _LOGGER.debug(
                        "Updated docker %s DPs from cmd_data",
                        device_id,
                    )
                elif group.device is not None:
                    group.device.dps = {
                        **group.device.dps,
                        **cmd_dps,
                    }
                    _LOGGER.debug(
                        "Updated device %s DPs from cmd_data",
                        device_id,
                    )
                self.data[group.id] = group
                data_updated = True

        # Notify entities of the in-place data change. Use async_update_listeners
        # rather than async_set_updated_data so a chatty device does not keep
        # resetting the 30s polling timer (which would starve BLE polling).
        if data_updated or topic.startswith("/device/DATA/"):
            self.async_update_listeners()

    def get_device_or_docker(self, device_id: str) -> Device | Docker | None:
        """Find the device or docker matching the given device ID."""
        for device in self.data.values():
            if device.device.device_id == device_id:
                return device.device
            if device.docker is not None and device.docker.docker_id == device_id:
                return device.docker
        return None

    def get_group(self, device_id: str) -> Group | None:
        """Find the group containing the device or docker with the given ID."""
        for device in self.data.values():
            if device.device.device_id == device_id:
                return device
            if device.docker is not None and device.docker.docker_id == device_id:
                return device
        return None

    async def send_write_command(self, group: Group, dp: GenericDP) -> bool:
        """Publish a command to a group's device (and docker, if present).

        Returns True only if every publish was accepted by the broker, so a
        dropped command is surfaced to the caller instead of being reported as
        a success.
        """
        command = {"ts": int(time.time()), "cmd": 4, "dp": [dp.dict()]}
        sent = await self.wybot_mqtt_client.send_write_command_for_device(
            group.device.device_id, command
        )
        if group.docker is not None:
            docker_sent = await self.wybot_mqtt_client.send_write_command_for_device(
                group.docker.docker_id, command
            )
            sent = sent and docker_sent
        return sent

    async def async_send_command(self, group: Group, dp: GenericDP) -> bool:
        """Send a command using BLE-first strategy with MQTT fallback.

        Attempts to send commands via BLE first (more reliable when WiFi is flaky).
        Falls back to MQTT if BLE fails or is disabled for this device.

        Args:
            group: The device group to send the command to
            dp: The GenericDP data point to send

        Returns:
            True if command was sent successfully via either BLE or MQTT
        """
        device_id = group.device.device_id
        ble_name = None

        # Prefer docker BLE name (dock has BLE, relays to robot)
        if group.docker and group.docker.ble_name:
            ble_name = group.docker.ble_name
        elif group.device and group.device.ble_name:
            ble_name = group.device.ble_name

        # Check if BLE should be recovered for this device
        self._maybe_recover_ble(device_id)

        # Check if BLE commands are enabled for this device
        ble_enabled = (
            self._ble_command_enabled
            and ble_name is not None
            and self._ble_command_failures.get(device_id, 0)
            < BLE_MAX_CONSECUTIVE_FAILURES
        )

        if ble_enabled:
            # ble_enabled is only True when ble_name is not None; narrow for typing.
            assert ble_name is not None
            _LOGGER.debug(
                "Attempting BLE-first command for device %s via %s (DP id=%d)",
                device_id,
                ble_name,
                dp.id,
            )
            try:
                ble_success, ble_dps = await self.wybot_ble_client.send_command(
                    ble_name, dp
                )

                if ble_success:
                    _LOGGER.debug(
                        "BLE command succeeded for device %s",
                        device_id,
                    )
                    # Reset failure count on success
                    self._ble_command_failures[device_id] = 0

                    # Update state from BLE response if we got DPs
                    if ble_dps:
                        self._update_from_ble_dps(group, device_id, ble_dps)

                    return True

                # BLE failed, increment failure count
                failures = self._ble_command_failures.get(device_id, 0) + 1
                self._ble_command_failures[device_id] = failures
                _LOGGER.warning(
                    "BLE command failed for device %s (failure %d/%d), falling back to MQTT",
                    device_id,
                    failures,
                    BLE_MAX_CONSECUTIVE_FAILURES,
                )

                if failures >= BLE_MAX_CONSECUTIVE_FAILURES:
                    self._ble_disabled_at[device_id] = time.time()
                    _LOGGER.warning(
                        "BLE commands disabled for device %s after %d consecutive failures (will retry in %ds)",
                        device_id,
                        failures,
                        BLE_RECOVERY_SECONDS,
                    )

            except Exception as err:  # noqa: BLE001
                # BLE failed with exception, increment failure count
                failures = self._ble_command_failures.get(device_id, 0) + 1
                self._ble_command_failures[device_id] = failures
                _LOGGER.warning(
                    "BLE command exception for device %s: %s (failure %d/%d), falling back to MQTT",
                    device_id,
                    err,
                    failures,
                    BLE_MAX_CONSECUTIVE_FAILURES,
                )
                if failures >= BLE_MAX_CONSECUTIVE_FAILURES:
                    self._ble_disabled_at[device_id] = time.time()
        elif ble_name is None:
            _LOGGER.debug(
                "No BLE name available for device %s, using MQTT",
                device_id,
            )
        elif not self._ble_command_enabled:
            _LOGGER.debug(
                "BLE commands globally disabled, using MQTT for device %s",
                device_id,
            )
        else:
            _LOGGER.debug(
                "BLE commands disabled for device %s (too many failures), using MQTT",
                device_id,
            )

        # Fallback to MQTT — make sure the fallback layer is actually connected
        # first, otherwise the command would be published to a dead client and
        # silently dropped (BLE-first startup leaves MQTT disconnected).
        if not await self._ensure_mqtt_connected():
            _LOGGER.warning(
                "MQTT fallback unavailable; command not sent for device %s", device_id
            )
            return False
        _LOGGER.debug(
            "Sending MQTT command for device %s (DP id=%d)",
            device_id,
            dp.id,
        )
        sent = await self.send_write_command(group, dp)
        if not sent:
            _LOGGER.warning("MQTT command was not published for device %s", device_id)
        return sent

    def reset_ble_command_failures(self, device_id: str | None = None) -> None:
        """Reset BLE command failure count for a device or all devices.

        Args:
            device_id: Specific device to reset, or None to reset all
        """
        if device_id:
            self._ble_command_failures.pop(device_id, None)
            _LOGGER.info("Reset BLE command failures for device %s", device_id)
        else:
            self._ble_command_failures.clear()
            _LOGGER.info("Reset BLE command failures for all devices")

    def _update_from_ble_dps(
        self, group: Group, device_id: str, dps: list[dict[str, Any]]
    ) -> None:
        """Update device state from BLE response DPs.

        Args:
            group: The device group to update
            device_id: The device ID
            dps: List of DP dicts from BLE response
        """
        if not dps:
            return

        try:
            # Create a command-like structure to reuse existing DP processing
            cmd_data: dict[str, Any] = {"cmd": 5, "ts": 0, "dp": dps}
            command = Command(**cmd_data)

            dp_dict: dict[str, Any] = command.get_dps_as_keyed_dict()

            # Update the appropriate device/docker
            if group.docker and group.docker.docker_id == device_id:
                group.docker.dps = {**group.docker.dps, **dp_dict}
                _LOGGER.debug(
                    "Updated docker %s DPs from BLE response",
                    device_id,
                )
            elif group.device:
                group.device.dps = {**group.device.dps, **dp_dict}
                _LOGGER.debug(
                    "Updated device %s DPs from BLE response",
                    device_id,
                )

            # This data arrived over BLE, so record it as BLE communication
            # (not MQTT) to keep the diagnostic sensors reporting the right
            # transport.
            self._last_ble_poll[device_id] = dt_util.utcnow()
            self._data_source[device_id] = "ble"

            # Trigger a state update
            self.async_set_updated_data(self.data)

        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Error updating state from BLE DPs: %s", err)

    async def query_all_device_status(self) -> None:
        """Query status for all devices by sending individual DP queries."""
        for device_id in self.data:
            group = self.data[device_id]
            if self.wybot_mqtt_client.is_connected():
                await self.wybot_mqtt_client.ensure_device_sends_statuses(
                    group.device.device_id
                )
                if group.docker is not None:
                    await self.wybot_mqtt_client.ensure_device_sends_statuses(
                        group.docker.docker_id
                    )

    @property
    def available(self) -> bool:
        """Return if the coordinator is available."""
        return self._connection_available and bool(self.data)

    @property
    def vacuums(self) -> list[str]:
        """Return a list of vacuum device ids.

        Right now we only support WyBot vacuums so we return everything, but this could be expanded
        """
        return list(self.data)
