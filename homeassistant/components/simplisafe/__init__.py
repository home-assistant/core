"""Support for SimpliSafe alarm systems."""

import asyncio
from typing import Any

from simplipy import API
from simplipy.errors import (
    EndpointUnavailableError,
    InvalidCredentialsError,
    RequestError,
    SimplipyError,
    WebsocketError,
)
from simplipy.system import SystemNotification
from simplipy.websocket import (
    EVENT_AUTOMATIC_TEST,
    EVENT_CAMERA_MOTION_DETECTED,
    EVENT_DEVICE_TEST,
    EVENT_DOORBELL_DETECTED,
    EVENT_SECRET_ALERT_TRIGGERED,
    EVENT_SENSOR_PAIRED_AND_NAMED,
    EVENT_USER_INITIATED_TEST,
    WebsocketEvent,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_CODE,
    CONF_CODE,
    CONF_TOKEN,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    aiohttp_client,
    config_validation as cv,
    device_registry as dr,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import (
    ATTR_LAST_EVENT_INFO,
    ATTR_LAST_EVENT_SENSOR_NAME,
    ATTR_LAST_EVENT_SENSOR_TYPE,
    ATTR_LAST_EVENT_TIMESTAMP,
    ATTR_SYSTEM_ID,
    DISPATCHER_TOPIC_WEBSOCKET_EVENT,
    DOMAIN,
    LOGGER,
)
from .coordinator import SimpliSafeDataUpdateCoordinator
from .services import async_setup_services
from .typing import SystemType

type SimpliSafeConfigEntry = ConfigEntry[SimpliSafe]

ATTR_CATEGORY = "category"
ATTR_LAST_EVENT_CHANGED_BY = "last_event_changed_by"
ATTR_LAST_EVENT_SENSOR_SERIAL = "last_event_sensor_serial"
ATTR_LAST_EVENT_TYPE = "last_event_type"
ATTR_LAST_EVENT_TYPE = "last_event_type"
ATTR_MESSAGE = "message"
ATTR_TIMESTAMP = "timestamp"

WEBSOCKET_RECONNECT_RETRIES = 3
WEBSOCKET_RETRY_DELAY = 2
WEBSOCKET_LOOP_TASK_NAME = "simplisafe websocket task"

EVENT_SIMPLISAFE_EVENT = "SIMPLISAFE_EVENT"
EVENT_SIMPLISAFE_NOTIFICATION = "SIMPLISAFE_NOTIFICATION"

PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.LOCK,
    Platform.SENSOR,
]


WEBSOCKET_EVENTS_TO_FIRE_HASS_EVENT = [
    EVENT_AUTOMATIC_TEST,
    EVENT_CAMERA_MOTION_DETECTED,
    EVENT_DOORBELL_DETECTED,
    EVENT_DEVICE_TEST,
    EVENT_SECRET_ALERT_TRIGGERED,
    EVENT_SENSOR_PAIRED_AND_NAMED,
    EVENT_USER_INITIATED_TEST,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration."""
    async_setup_services(hass)
    return True


@callback
def _async_register_base_station(
    hass: HomeAssistant, entry: ConfigEntry, system: SystemType
) -> None:
    """Register a new bridge."""
    device_registry = dr.async_get(hass)

    base_station = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, str(system.system_id))},
        manufacturer="SimpliSafe",
        model=str(system.version),
        name=system.address,
    )

    # Check for an old system ID format and remove it:
    if old_base_station := device_registry.async_get_device_by_identifier(
        (DOMAIN, system.system_id),  # type: ignore[arg-type]
        entry.entry_id,
    ):
        # Update the new base station with any properties the user might have configured
        # on the old base station:
        device_registry.async_update_device(
            base_station.id,
            area_id=old_base_station.area_id,
            disabled_by=old_base_station.disabled_by,
            name_by_user=old_base_station.name_by_user,
        )
        device_registry.async_remove_device(old_base_station.id)


@callback
def _async_standardize_config_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Bring a config entry up to current standards."""
    if CONF_TOKEN not in entry.data:
        raise ConfigEntryAuthFailed(
            "SimpliSafe OAuth standard requires re-authentication"
        )

    entry_updates = {}
    if not entry.unique_id:
        # If the config entry doesn't already have a unique ID, set one:
        entry_updates["unique_id"] = entry.data[CONF_USERNAME]
    if CONF_CODE in entry.data:
        # If an alarm code was provided as part of configuration.yaml, pop it out of
        # the config entry's data and move it to options:
        data = {**entry.data}
        entry_updates["data"] = data
        entry_updates["options"] = {
            **entry.options,
            CONF_CODE: data.pop(CONF_CODE),
        }
    if entry_updates:
        hass.config_entries.async_update_entry(entry, **entry_updates)


async def async_setup_entry(hass: HomeAssistant, entry: SimpliSafeConfigEntry) -> bool:
    """Set up SimpliSafe as config entry."""
    _async_standardize_config_entry(hass, entry)

    websession = aiohttp_client.async_get_clientsession(hass)

    try:
        api = await API.async_from_refresh_token(
            entry.data[CONF_TOKEN], session=websession
        )
    except InvalidCredentialsError as err:
        raise ConfigEntryAuthFailed from err
    except SimplipyError as err:
        LOGGER.error("Config entry failed: %s", err)
        raise ConfigEntryNotReady from err

    simplisafe = SimpliSafe(hass, entry, api)

    try:
        await simplisafe.async_init()
    except SimplipyError as err:
        raise ConfigEntryNotReady from err

    entry.runtime_data = simplisafe

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    current_options = {**entry.options}

    async def async_reload_entry(_: HomeAssistant, updated_entry: ConfigEntry) -> None:
        """Handle an options update.

        This method will get called in two scenarios:
          1. When SimpliSafeOptionsFlowHandler is initiated
          2. When a new refresh token is saved to the config entry data

        We only want #1 to trigger an actual reload.
        """
        nonlocal current_options
        updated_options = {**updated_entry.options}

        if updated_options == current_options:
            return

        await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SimpliSafeConfigEntry) -> bool:
    """Unload a SimpliSafe config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class SimpliSafe:
    """Define a SimpliSafe data object."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: API) -> None:
        """Initialize."""
        self._api = api
        self._hass = hass
        self._system_notifications: dict[int, set[SystemNotification]] = {}
        self._websocket_task: asyncio.Task | None = None
        self.entry = entry
        self.initial_event_to_use: dict[int, dict[str, Any]] = {}
        self.subscription_data: dict[int, Any] = api.subscription_data
        self.systems: dict[int, SystemType] = {}

        # This will get filled in by async_init:
        self.coordinator: SimpliSafeDataUpdateCoordinator | None = None

    @callback
    def _async_process_new_notifications(self, system: SystemType) -> None:
        """Act on any new system notifications."""
        if self._hass.state is not CoreState.running:
            # If HASS isn't fully running yet, it may cause the SIMPLISAFE_NOTIFICATION
            # event to fire before dependent components (like automation) are fully
            # ready. If that's the case, skip:
            return

        latest_notifications = set(system.notifications)

        to_add = latest_notifications.difference(
            self._system_notifications[system.system_id]
        )

        if not to_add:
            return

        LOGGER.debug("New system notifications: %s", to_add)

        for notification in to_add:
            text = notification.text
            if notification.link:
                text = f"{text} For more information: {notification.link}"

            self._hass.bus.async_fire(
                EVENT_SIMPLISAFE_NOTIFICATION,
                event_data={
                    ATTR_CATEGORY: notification.category,
                    ATTR_CODE: notification.code,
                    ATTR_MESSAGE: text,
                    ATTR_TIMESTAMP: notification.timestamp,
                },
            )

        self._system_notifications[system.system_id] = latest_notifications

    @callback
    def _async_start_websocket_if_needed(self) -> None:
        """Start the websocket loop task if it isn't already running."""
        task = self._websocket_task

        if task and not task.done():
            return

        LOGGER.debug("Starting websocket loop task")

        self._websocket_task = self.entry.async_create_background_task(
            self._hass, self._async_websocket_loop(), WEBSOCKET_LOOP_TASK_NAME
        )

    async def _async_websocket_loop(self) -> None:
        assert self._api.websocket

        retries = 0
        while True:
            try:
                await self._api.websocket.async_connect()
                await self._api.websocket.async_listen()
            except asyncio.CancelledError:
                await self._api.websocket.async_disconnect()
                raise
            except WebsocketError as err:
                retries += 1
                delay = WEBSOCKET_RETRY_DELAY * (2 ** (retries - 1))
                LOGGER.debug(
                    "Websocket error (%s/%s): %s; retrying in %s seconds",
                    retries,
                    WEBSOCKET_RECONNECT_RETRIES,
                    err,
                    delay,
                )

                await asyncio.sleep(delay)
                if retries >= WEBSOCKET_RECONNECT_RETRIES:
                    LOGGER.error(
                        "Websocket connection failed, task exiting (%s/%s): %s",
                        retries,
                        WEBSOCKET_RECONNECT_RETRIES,
                        err,
                    )
                    return
            except Exception as err:  # noqa: BLE001
                # unexpected errors → log and stop
                LOGGER.exception("Unexpected error in websocket loop: %s", err)
                return

    async def _async_cancel_websocket_loop(self) -> None:
        """Cancel the websocket loop task, if running."""
        task = self._websocket_task
        if not task:
            return

        self._websocket_task = None
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            LOGGER.debug("Websocket loop task cancelled")

    @callback
    def _async_websocket_on_event(self, event: WebsocketEvent) -> None:
        """Define a callback for receiving a websocket event."""
        LOGGER.debug("New websocket event: %s", event)

        async_dispatcher_send(
            self._hass, DISPATCHER_TOPIC_WEBSOCKET_EVENT.format(event.system_id), event
        )

        if event.event_type not in WEBSOCKET_EVENTS_TO_FIRE_HASS_EVENT:
            return

        sensor_type: str | None
        if event.sensor_type:
            sensor_type = event.sensor_type.name
        else:
            sensor_type = None

        self._hass.bus.async_fire(
            EVENT_SIMPLISAFE_EVENT,
            event_data={
                ATTR_LAST_EVENT_CHANGED_BY: event.changed_by,
                ATTR_LAST_EVENT_TYPE: event.event_type,
                ATTR_LAST_EVENT_INFO: event.info,
                ATTR_LAST_EVENT_SENSOR_NAME: event.sensor_name,
                ATTR_LAST_EVENT_SENSOR_SERIAL: event.sensor_serial,
                ATTR_LAST_EVENT_SENSOR_TYPE: sensor_type,
                ATTR_SYSTEM_ID: event.system_id,
                ATTR_LAST_EVENT_TIMESTAMP: event.timestamp,
            },
        )

    async def async_init(self) -> None:
        """Initialize the SimpliSafe "manager" class."""
        assert self._api.refresh_token
        assert self._api.websocket

        self._api.websocket.add_event_callback(self._async_websocket_on_event)
        self._async_start_websocket_if_needed()

        self.systems = await self._api.async_get_systems()
        for system in self.systems.values():
            self._system_notifications[system.system_id] = set()

            _async_register_base_station(self._hass, self.entry, system)

            # Future events will come from the websocket, but since subscription to the
            # websocket doesn't provide the most recent event, we grab it from the REST
            # API to ensure event-related attributes aren't empty on startup:
            try:
                self.initial_event_to_use[
                    system.system_id
                ] = await system.async_get_latest_event()
            except SimplipyError as err:
                LOGGER.error("Error while fetching initial event: %s", err)
                self.initial_event_to_use[system.system_id] = {}

        self.coordinator = SimpliSafeDataUpdateCoordinator(
            self._hass,
            self.entry,
            name=self.entry.title,
            simplisafe=self,
        )

        @callback
        def async_save_refresh_token(token: str) -> None:
            """Save a refresh token to the config entry."""
            LOGGER.debug("Saving new refresh token to HASS storage")
            self._hass.config_entries.async_update_entry(
                self.entry,
                data={**self.entry.data, CONF_TOKEN: token},
            )

        async def async_handle_refresh_token(token: str) -> None:
            """Handle a new refresh token."""
            async_save_refresh_token(token)

            # Open a new websocket connection with the fresh token:
            assert self._api.websocket
            await self._async_cancel_websocket_loop()
            self._async_start_websocket_if_needed()

        self.entry.async_on_unload(
            self._api.add_refresh_token_callback(async_handle_refresh_token)
        )

        # Save the refresh token we got on entry setup:
        async_save_refresh_token(self._api.refresh_token)

    async def async_update(self) -> None:
        """Get updated data from SimpliSafe."""

        async def async_update_system(system: SystemType) -> None:
            """Update a single system and process notifications."""
            await system.async_update(cached=system.version != 3)
            self._async_process_new_notifications(system)

        tasks = [async_update_system(system) for system in self.systems.values()]

        try:
            # Gather all system updates; exceptions will propagate
            await asyncio.gather(*tasks)
        except InvalidCredentialsError as err:
            # Stop websocket immediately on auth failure
            if self._websocket_task:
                LOGGER.debug("Cancelling websocket loop due to invalid credentials")
                await self._async_cancel_websocket_loop()
            # Signal HA that credentials are invalid; user intervention is required
            raise ConfigEntryAuthFailed("Invalid credentials") from err
        except RequestError as err:
            # Cloud-level request errors: wrap aiohttp errors
            if self._websocket_task:
                LOGGER.debug("Cancelling websocket loop due to request error")
                await self._async_cancel_websocket_loop()
            raise UpdateFailed(
                f"Request error while updating all systems: {err}"
            ) from err
        except EndpointUnavailableError as err:
            # Currently not raised by the API; included for future-proofing.
            # Informational per-system (e.g., user plan restrictions)
            LOGGER.debug("Endpoint unavailable: %s", err)
        except SimplipyError as err:
            # Any other SimplipyError not caught per-system
            raise UpdateFailed(f"SimpliSafe error while updating: {err}") from err
        else:
            # Successful update, try to restart websocket if necessary
            self._async_start_websocket_if_needed()
