"""Data update coordinator for the Nest Legacy integration."""

from __future__ import annotations

import asyncio
from collections import deque
import logging
import random
import time
from typing import Any

from aiohttp import ClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCOUNT_TYPE,
    CONF_COOKIES,
    CONF_ENABLE_PROTOBUF_CAMERA,
    CONF_ENABLE_PROTOBUF_LOCK,
    CONF_ENABLE_PROTOBUF_PROTECT,
    CONF_ENABLE_PROTOBUF_STRUCTURE,
    CONF_ENABLE_PROTOBUF_THERMOSTAT,
    CONF_EVENT_POLL_INTERVAL,
    CONF_FIELD_TEST,
    CONF_ISSUE_TOKEN,
    DEFAULT_EVENT_POLL_INTERVAL,
    DOMAIN,
)
from .events import NEST_LEGACY_EVENT
from .pynest.client import NestClient
from .pynest.exceptions import (
    BadCredentialsException,
    EmptyResponseException,
    NotAuthenticatedException,
    PynestException,
)
from .pynest.models import NestCamera, NestDevice, NestHeatLink, NestTempSensor
from .pynest.parser import NestParser

_LOGGER = logging.getLogger(__name__)

MAX_EVENT_AGE_SECONDS = 60
MAX_BACKOFF_SECONDS = 60
INITIAL_BACKOFF_SECONDS = 0.1


type NestConfigEntry = ConfigEntry[NestCoordinator]


class NestCoordinator(DataUpdateCoordinator[dict[str, NestDevice]]):
    """Manages fetching and processing Nest data."""

    config_entry: NestConfigEntry
    client: NestClient
    parser: NestParser

    def __init__(self, hass: HomeAssistant, entry: NestConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,  # This coordinator is push-based (except for events)
            config_entry=entry,
        )
        self.client = NestClient(
            async_create_clientsession(hass),
            field_test=entry.data.get(CONF_FIELD_TEST, False),
            enable_protobuf_lock=entry.options.get(CONF_ENABLE_PROTOBUF_LOCK, True),
            enable_protobuf_thermostat=entry.options.get(
                CONF_ENABLE_PROTOBUF_THERMOSTAT, True
            ),
            enable_protobuf_structure=entry.options.get(
                CONF_ENABLE_PROTOBUF_STRUCTURE, False
            ),
            enable_protobuf_protect=entry.options.get(
                CONF_ENABLE_PROTOBUF_PROTECT, False
            ),
            enable_protobuf_camera=entry.options.get(
                CONF_ENABLE_PROTOBUF_CAMERA,
                entry.data.get(CONF_ACCOUNT_TYPE) == "google",
            ),
        )
        self.parser = NestParser()
        self._subscribe_task: asyncio.Task | None = None
        self._observe_task: asyncio.Task | None = None
        self._poll_task: asyncio.Task | None = None
        self._raw_data: dict[str, Any] = {}
        self._processed_event_ids: deque[str] = deque(maxlen=1000)
        self._last_event_poll_success_time: float | None = None
        self.first_protobuf_update_received = asyncio.Event()
        self._auth_lock = asyncio.Lock()
        self._subscriber_unavailable_logged = False
        self._observer_unavailable_logged = False

    def get_raw_data_for_diagnostics(self) -> dict[str, Any]:
        """Return raw data, useful for diagnostics."""
        return self._raw_data

    async def async_reauthenticate(self, force: bool = False) -> None:
        """(Re-)authenticate with the Nest API."""
        async with self._auth_lock:
            if not force and not self.client.is_expired():
                return
            data = self.config_entry.data
            account_type = data.get(CONF_ACCOUNT_TYPE)
            if account_type == "google":
                await self.client.async_authenticate_with_google_credentials(
                    data[CONF_ISSUE_TOKEN], data[CONF_COOKIES]
                )
            elif account_type == "nest":
                await self.client.async_authenticate_with_nest_token(
                    data[CONF_ACCESS_TOKEN]
                )
            else:
                raise HomeAssistantError(
                    f"Unsupported account type in config entry: {account_type}"
                )

    async def async_initialize(self) -> None:
        """Initialize the connection and fetch initial data."""
        try:
            await self.async_reauthenticate()
            self._raw_data = await self.client.async_get_first_data()
            parsed_data = self.parser.parse_all(self._raw_data)
            self.data = {
                **{device.serial_number: device for device in parsed_data.devices},
            }

            # Fetch detailed properties for any cameras found in the initial data
            camera_property_tasks = [
                self._async_update_camera_properties(device)
                for device in self.data.values()
                if isinstance(device, NestCamera)
            ]
            if camera_property_tasks:
                await asyncio.gather(*camera_property_tasks)
                # Re-parse data after fetching additional properties
                parsed_data = self.parser.parse_all(self._raw_data)
                self.data = {
                    **{device.serial_number: device for device in parsed_data.devices},
                }

        except BadCredentialsException as err:
            raise ConfigEntryAuthFailed from err
        except (ClientError, TimeoutError, PynestException) as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def async_set_device_data(
        self, device: NestDevice, data: dict[str, Any]
    ) -> None:
        """Set device data and handle exceptions."""
        # For Protobuf devices, we need to pass the current raw traits to the client
        # to ensure we don't overwrite existing fields with defaults.
        current_traits = None
        if device.is_protobuf:
            resource_id = device.object_key
            # HeatLinks and Temp Sensors are controlled via their associated thermostat resource
            if (
                isinstance(device, (NestHeatLink, NestTempSensor))
                and device.associated_thermostat_object_key
            ):
                resource_id = device.associated_thermostat_object_key

            current_traits = self._raw_data.get(resource_id)

        try:
            await self.client.async_set_device_data(
                device, data, current_traits=current_traits
            )
        except NotAuthenticatedException:
            _LOGGER.debug(
                "Token expired during command. Re-authenticating and retrying"
            )
            try:
                await self.async_reauthenticate(force=True)
                await self.client.async_set_device_data(
                    device, data, current_traits=current_traits
                )
            except (ClientError, TimeoutError, PynestException) as err:
                raise HomeAssistantError(
                    "Retry failed after re-authentication"
                ) from err
        except (ClientError, TimeoutError, PynestException) as err:
            _LOGGER.error(
                "Error setting data for Nest device %s %s (%s) with payload %s: %r",
                device.location,
                device.name,
                device.serial_number,
                data,
                err,
            )
            raise HomeAssistantError from err

    def async_start_subscriber(self) -> None:
        """Start the background task to listen for updates."""
        if self._subscribe_task is None:
            self._subscribe_task = self.config_entry.async_create_background_task(
                self.hass, self._async_subscribe_for_updates(), "nest-subscribe-rest"
            )
            self._observe_task = self.config_entry.async_create_background_task(
                self.hass, self._async_observe_for_updates(), "nest-observe-protobuf"
            )
            self._poll_task = self.config_entry.async_create_background_task(
                self.hass, self._async_poll_camera_events(), "nest-poll-events"
            )

    def async_stop_subscriber(self) -> None:
        """Stop the background task."""
        if self._subscribe_task:
            self._subscribe_task.cancel()
            self._subscribe_task = None
        if self._observe_task:
            self._observe_task.cancel()
            self._observe_task = None
        if self._poll_task:
            self._poll_task.cancel()
            self._poll_task = None

    def _debug_log_diff(
        self, key: str, old_val: dict[Any, Any], new_val: dict[Any, Any]
    ) -> None:
        """Log the differences between two dictionaries for debugging."""
        if not _LOGGER.isEnabledFor(logging.DEBUG):
            return
        _LOGGER.debug("Received update with changes for %s:", key)
        old_keys = set(old_val.keys())
        new_keys = set(new_val.keys())
        for k in sorted(new_keys - old_keys):
            _LOGGER.debug("  + %s: %s", k, new_val[k])
        for k in sorted(old_keys - new_keys):
            _LOGGER.debug("  - %s: %s", k, old_val[k])
        for k in sorted(old_keys & new_keys):
            if old_val[k] != new_val[k]:
                _LOGGER.debug("  ~ %s: %s -> %s", k, old_val[k], new_val[k])

    async def _async_subscribe_for_updates(self) -> None:
        """Listen for data updates from the Nest API."""
        failures = 0
        force_reauth = False
        while True:
            try:
                if self.client.is_expired() or force_reauth:
                    _LOGGER.debug("Re-authenticating Nest session")
                    await self.async_reauthenticate(force_reauth)
                    force_reauth = False  # Reset on success

                updates = await self.client.async_subscribe_for_updates()
                failures = 0  # Reset on success

                if not updates:
                    continue

                if self._subscriber_unavailable_logged:
                    _LOGGER.info("Nest subscriber connection restored")
                    self._subscriber_unavailable_logged = False

                camera_property_tasks = []
                for key, value in updates.items():
                    old_value = self._raw_data.get(key)
                    if old_value == value:
                        _LOGGER.debug("Received update with no changes for %s", key)
                        continue
                    if (
                        old_value
                        and isinstance(old_value, dict)
                        and isinstance(value, dict)
                    ):
                        self._debug_log_diff(key, old_value, value)
                    else:
                        _LOGGER.debug("Received update for %s: %s", key, value)
                    self._raw_data[key] = value

                    # If this is a camera, also fetch its detailed properties
                    if (serial := value.get("serial_number")) and isinstance(
                        serial, str
                    ):
                        device = self.data.get(serial)
                        if isinstance(device, NestCamera):
                            camera_property_tasks.append(
                                self._async_update_camera_properties(device)
                            )

                if camera_property_tasks:
                    await asyncio.gather(*camera_property_tasks)

                parsed_data = self.parser.parse_all(self._raw_data)
                new_devices = {
                    device.serial_number: device for device in parsed_data.devices
                }

                # Clean up stale devices
                device_registry = dr.async_get(self.hass)
                current_devices = dr.async_entries_for_config_entry(
                    device_registry, self.config_entry.entry_id
                )
                for device_entry in current_devices:
                    # Identifier is a tuple (DOMAIN, serial_number)
                    serial_number = next(iter(device_entry.identifiers))[1]
                    if serial_number not in new_devices:
                        _LOGGER.debug("Removing stale device %s", serial_number)
                        device_registry.async_update_device(
                            device_id=device_entry.id,
                            remove_config_entry_id=self.config_entry.entry_id,
                        )

                # If a new device was discovered during the update, reload the integration
                if set(new_devices.keys()) - set(self.data.keys()):
                    _LOGGER.info("New Nest device discovered. Reloading integration")
                    self.hass.async_create_task(
                        self.hass.config_entries.async_reload(
                            self.config_entry.entry_id
                        )
                    )

                self.data = new_devices
                self.async_set_updated_data(self.data)

            except NotAuthenticatedException:
                _LOGGER.debug("Subscriber not authenticated. Re-authenticating")
                force_reauth = True
                await asyncio.sleep(INITIAL_BACKOFF_SECONDS)
                continue
            except BadCredentialsException:
                _LOGGER.error("Bad credentials, re-authentication required")
                self.config_entry.async_start_reauth(self.hass)
                self.async_stop_subscriber()
                return
            except TimeoutError, EmptyResponseException:
                _LOGGER.debug("Subscriber connection timeout (expected). Reconnecting")
                failures = 0
                continue
            except Exception as err:
                delay = min(
                    MAX_BACKOFF_SECONDS,
                    INITIAL_BACKOFF_SECONDS * (2**failures),
                )
                failures += 1
                if isinstance(err, (ClientError, PynestException)):
                    if not self._subscriber_unavailable_logged:
                        _LOGGER.warning(
                            "Subscriber connection error: %r. Retrying in %ds",
                            err,
                            delay,
                        )
                        self._subscriber_unavailable_logged = True
                    else:
                        _LOGGER.debug(
                            "Subscriber connection error: %r. Retrying in %ds",
                            err,
                            delay,
                        )
                elif not self._subscriber_unavailable_logged:
                    _LOGGER.exception(
                        "Unknown exception in subscriber. Retrying in %ds", delay
                    )
                    self._subscriber_unavailable_logged = True
                else:
                    _LOGGER.debug(
                        "Unknown exception in subscriber: %r. Retrying in %ds",
                        err,
                        delay,
                    )
                await asyncio.sleep(delay)
                continue

    async def _async_observe_for_updates(self) -> None:
        """Listen for protobuf data updates from the Nest API."""
        failures = 0
        force_reauth = False
        while True:
            try:
                if self.client.is_expired() or force_reauth:
                    _LOGGER.debug("Re-authenticating Nest session for observe")
                    await self.async_reauthenticate(force_reauth)
                    force_reauth = False  # Reset on success

                async for updates in self.client.async_observe_for_updates():
                    failures = 0  # Reset on success

                    if self._observer_unavailable_logged:
                        _LOGGER.info("Nest observer connection restored")
                        self._observer_unavailable_logged = False

                    # Deep merge protobuf updates into raw_data
                    for resource_id, traits in updates.items():
                        if resource_id not in self._raw_data:
                            self._raw_data[resource_id] = {}
                        for trait_label, trait_data in traits.items():
                            if _LOGGER.isEnabledFor(logging.DEBUG):
                                old_trait_data = self._raw_data[resource_id].get(
                                    trait_label
                                )
                                if old_trait_data != trait_data:
                                    _LOGGER.debug(
                                        "Protobuf change for %s/%s: %s -> %s",
                                        resource_id,
                                        trait_label,
                                        old_trait_data,
                                        trait_data,
                                    )
                            self._raw_data[resource_id][trait_label] = trait_data

                    parsed_data = self.parser.parse_all(self._raw_data)
                    new_devices = {
                        device.serial_number: device for device in parsed_data.devices
                    }

                    # Clean up stale devices
                    device_registry = dr.async_get(self.hass)
                    current_devices = dr.async_entries_for_config_entry(
                        device_registry, self.config_entry.entry_id
                    )
                    for device_entry in current_devices:
                        serial_number = next(iter(device_entry.identifiers))[1]
                        if serial_number not in new_devices:
                            _LOGGER.debug(
                                "Removing stale device %s via observer", serial_number
                            )
                            device_registry.async_update_device(
                                device_id=device_entry.id,
                                remove_config_entry_id=self.config_entry.entry_id,
                            )

                    if self.first_protobuf_update_received.is_set() and set(
                        new_devices.keys()
                    ) - set(self.data.keys()):
                        _LOGGER.info(
                            "New Nest device discovered via Protobuf. Reloading integration"
                        )
                        self.hass.async_create_task(
                            self.hass.config_entries.async_reload(
                                self.config_entry.entry_id
                            )
                        )

                    self.data = new_devices
                    self.async_set_updated_data(self.data)

                    # On first update, signal readiness and decide if we need to continue observing.
                    if not self.first_protobuf_update_received.is_set():
                        _LOGGER.debug("Received first protobuf update")
                        self.first_protobuf_update_received.set()

                        # If no protobuf-enabled devices were discovered, stop observing.
                        if not any(device.is_protobuf for device in self.data.values()):
                            _LOGGER.debug(
                                "No protobuf-enabled devices found in initial data; stopping observer task"
                            )
                            return  # Exit the while loop and terminate the task.

            except NotAuthenticatedException:
                _LOGGER.debug("Observer not authenticated. Re-authenticating")
                force_reauth = True
                await asyncio.sleep(INITIAL_BACKOFF_SECONDS)
                continue
            except BadCredentialsException:
                _LOGGER.error(
                    "Bad credentials for observer, re-authentication required"
                )
                self.config_entry.async_start_reauth(self.hass)
                self.async_stop_subscriber()
                return
            except Exception as err:
                delay = min(
                    MAX_BACKOFF_SECONDS,
                    INITIAL_BACKOFF_SECONDS * (2**failures),
                )
                failures += 1
                if isinstance(err, (ClientError, TimeoutError, PynestException)):
                    if not self._observer_unavailable_logged:
                        _LOGGER.warning(
                            "Observer connection error: %r. Retrying in %ds", err, delay
                        )
                        self._observer_unavailable_logged = True
                    else:
                        _LOGGER.debug(
                            "Observer connection error: %r. Retrying in %ds", err, delay
                        )
                elif not self._observer_unavailable_logged:
                    _LOGGER.exception(
                        "Unknown exception in observer. Retrying in %ds", delay
                    )
                    self._observer_unavailable_logged = True
                else:
                    _LOGGER.debug(
                        "Unknown exception in observer: %r. Retrying in %ds",
                        err,
                        delay,
                    )
                await asyncio.sleep(delay)
                continue

    async def _async_poll_camera_events(self) -> None:
        """Poll the camera cuepoint API for events."""
        failures = 0
        while True:
            poll_interval = self.config_entry.options.get(
                CONF_EVENT_POLL_INTERVAL, DEFAULT_EVENT_POLL_INTERVAL
            )
            loop_start = time.time()

            try:
                # Determine the start time for the event query
                last_success = self._last_event_poll_success_time or (
                    time.time() - MAX_EVENT_AGE_SECONDS
                )
                # Use last success time with a buffer, but don't look back more than 60s
                start_time = max(
                    last_success - poll_interval,
                    time.time() - MAX_EVENT_AGE_SECONDS,
                )

                # Gather all camera event tasks
                tasks = [
                    self._async_process_events_for_device(
                        device, start_time, poll_interval
                    )
                    for device in self.data.values()
                    if isinstance(device, NestCamera)
                    and device.online
                    and device.streaming_enabled
                ]
                if tasks:
                    await asyncio.gather(*tasks)

                self._last_event_poll_success_time = time.time()
                failures = 0  # Reset on success
            except Exception as err:
                delay = min(
                    MAX_BACKOFF_SECONDS,
                    INITIAL_BACKOFF_SECONDS * (2**failures),
                )
                failures += 1
                if isinstance(err, TimeoutError):
                    _LOGGER.debug(
                        "Error polling for events: %r. Retrying in %ds", err, delay
                    )
                elif isinstance(err, (ClientError, PynestException)):
                    _LOGGER.warning(
                        "Error polling for events: %r. Retrying in %ds", err, delay
                    )
                else:
                    _LOGGER.exception(
                        "Unknown error polling for events. Retrying in %ds", delay
                    )
                await asyncio.sleep(delay)
                continue

            # Calculate remaining sleep time to eliminate drift
            elapsed = time.time() - loop_start
            sleep_time = max(0.0, poll_interval - elapsed)
            await asyncio.sleep(sleep_time)

    async def _async_process_events_for_device(
        self, device: NestCamera, start_time: float, poll_interval: float
    ) -> None:
        """Fetch and process events for a single camera."""
        # Add jitter to spread out API calls
        jitter_limit = max(0, poll_interval - 1)
        if jitter_limit > 0:
            await asyncio.sleep(random.uniform(0, jitter_limit))

        try:
            events = await self.client.async_get_camera_events(
                device, start_time=int(start_time)
            )
        except (ClientError, TimeoutError, PynestException) as err:
            _LOGGER.warning(
                "Error fetching events for camera %s %s: %r",
                device.location,
                device.name,
                err,
            )
            return
        if not events:
            return

        # Sort by start_time so we process oldest to newest
        events = sorted(events, key=lambda ev: ev.get("start_time", 0))

        for event in events:
            event_id = event.get("id")
            if not event_id or event_id in self._processed_event_ids:
                continue

            self._processed_event_ids.append(event_id)

            _LOGGER.debug(
                "New event for %s %s: %s", device.location, device.name, event
            )

            self.hass.bus.async_fire(
                NEST_LEGACY_EVENT,
                {
                    "serial_number": device.serial_number,
                    "nest_event": event,
                },
            )

            # CRITICAL: Prevent distinct historical events from firing in the exact
            # same millisecond, which causes HA to drop them as duplicates.
            await asyncio.sleep(0.001)

    async def _async_update_camera_properties(self, device: NestCamera) -> None:
        """Update the detailed properties for a single camera."""
        try:
            properties = await self.client.async_get_camera_properties(device)
            if not properties:
                return
            # Merge properties into the main device bucket
            device_bucket = self._raw_data.get(device.object_key, {})
            if "properties" not in device_bucket:
                device_bucket["properties"] = {}
            device_bucket["properties"].update(properties)
        except (ClientError, TimeoutError, PynestException) as err:
            _LOGGER.warning(
                "Error fetching properties for camera %s %s: %r",
                device.location,
                device.name,
                err,
            )

    async def _async_update_data(self) -> dict[str, NestDevice]:
        """Update data via the coordinator.

        This method is not used for polling but can be triggered manually.
        For Nest, updates are push-based via the subscriber.
        """
        return self.data
