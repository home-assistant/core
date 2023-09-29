"""Support for SimpliSafe alarm systems."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from datetime import timedelta
from typing import Any, cast

from simplipy import API
from simplipy.device import Device, DeviceTypes
from simplipy.errors import (
    EndpointUnavailableError,
    InvalidCredentialsError,
    SimplipyError,
    WebsocketError,
)
from simplipy.system import SystemNotification
from simplipy.system.v3 import (
    MAX_ALARM_DURATION,
    MAX_ENTRY_DELAY_AWAY,
    MAX_ENTRY_DELAY_HOME,
    MAX_EXIT_DELAY_AWAY,
    MAX_EXIT_DELAY_HOME,
    MIN_ALARM_DURATION,
    MIN_ENTRY_DELAY_AWAY,
    MIN_EXIT_DELAY_AWAY,
    SystemV3,
    Volume,
)
from simplipy.websocket import (
    EVENT_AUTOMATIC_TEST,
    EVENT_CAMERA_MOTION_DETECTED,
    EVENT_CONNECTION_LOST,
    EVENT_CONNECTION_RESTORED,
    EVENT_DEVICE_TEST,
    EVENT_DOORBELL_DETECTED,
    EVENT_LOCK_LOCKED,
    EVENT_LOCK_UNLOCKED,
    EVENT_POWER_OUTAGE,
    EVENT_POWER_RESTORED,
    EVENT_SECRET_ALERT_TRIGGERED,
    EVENT_SENSOR_PAIRED_AND_NAMED,
    EVENT_USER_INITIATED_TEST,
    WebsocketEvent,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    ATTR_CODE,
    ATTR_DEVICE_ID,
    CONF_CODE,
    CONF_TOKEN,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import CoreState, Event, HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import (
    aiohttp_client,
    config_validation as cv,
    device_registry as dr,
)
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.service import (
    async_register_admin_service,
    verify_domain_control,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    ATTR_ALARM_DURATION,
    ATTR_ALARM_VOLUME,
    ATTR_CHIME_VOLUME,
    ATTR_ENTRY_DELAY_AWAY,
    ATTR_ENTRY_DELAY_HOME,
    ATTR_EXIT_DELAY_AWAY,
    ATTR_EXIT_DELAY_HOME,
    ATTR_LIGHT,
    ATTR_VOICE_PROMPT_VOLUME,
    DOMAIN,
    LOGGER,
)
from .typing import SystemType

ATTR_CATEGORY = "category"
ATTR_LAST_EVENT_CHANGED_BY = "last_event_changed_by"
ATTR_LAST_EVENT_INFO = "last_event_info"
ATTR_LAST_EVENT_SENSOR_NAME = "last_event_sensor_name"
ATTR_LAST_EVENT_SENSOR_SERIAL = "last_event_sensor_serial"
ATTR_LAST_EVENT_SENSOR_TYPE = "last_event_sensor_type"
ATTR_LAST_EVENT_TIMESTAMP = "last_event_timestamp"
ATTR_LAST_EVENT_TYPE = "last_event_type"
ATTR_LAST_EVENT_TYPE = "last_event_type"
ATTR_MESSAGE = "message"
ATTR_PIN_LABEL = "label"
ATTR_PIN_LABEL_OR_VALUE = "label_or_pin"
ATTR_PIN_VALUE = "pin"
ATTR_SYSTEM_ID = "system_id"
ATTR_TIMESTAMP = "timestamp"

DEFAULT_CONFIG_URL = "https://webapp.simplisafe.com/new/#/dashboard"
DEFAULT_ENTITY_MODEL = "Alarm control panel"
DEFAULT_ERROR_THRESHOLD = 2
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)
DEFAULT_SOCKET_MIN_RETRY = 15

DISPATCHER_TOPIC_WEBSOCKET_EVENT = "simplisafe_websocket_event_{0}"

EVENT_SIMPLISAFE_EVENT = "SIMPLISAFE_EVENT"
EVENT_SIMPLISAFE_NOTIFICATION = "SIMPLISAFE_NOTIFICATION"

PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.LOCK,
    Platform.SENSOR,
]

VOLUME_MAP = {
    "high": Volume.HIGH,
    "low": Volume.LOW,
    "medium": Volume.MEDIUM,
    "off": Volume.OFF,
}

SERVICE_NAME_REMOVE_PIN = "remove_pin"
SERVICE_NAME_SET_PIN = "set_pin"
SERVICE_NAME_SET_SYSTEM_PROPERTIES = "set_system_properties"

SERVICES = (
    SERVICE_NAME_REMOVE_PIN,
    SERVICE_NAME_SET_PIN,
    SERVICE_NAME_SET_SYSTEM_PROPERTIES,
)

SERVICE_REMOVE_PIN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_PIN_LABEL_OR_VALUE): cv.string,
    }
)

SERVICE_SET_PIN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_PIN_LABEL): cv.string,
        vol.Required(ATTR_PIN_VALUE): cv.string,
    },
)

SERVICE_SET_SYSTEM_PROPERTIES_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional(ATTR_ALARM_DURATION): vol.All(
            cv.time_period,
            lambda value: value.total_seconds(),
            vol.Range(min=MIN_ALARM_DURATION, max=MAX_ALARM_DURATION),
        ),
        vol.Optional(ATTR_ALARM_VOLUME): vol.All(vol.In(VOLUME_MAP), VOLUME_MAP.get),
        vol.Optional(ATTR_CHIME_VOLUME): vol.All(vol.In(VOLUME_MAP), VOLUME_MAP.get),
        vol.Optional(ATTR_ENTRY_DELAY_AWAY): vol.All(
            cv.time_period,
            lambda value: value.total_seconds(),
            vol.Range(min=MIN_ENTRY_DELAY_AWAY, max=MAX_ENTRY_DELAY_AWAY),
        ),
        vol.Optional(ATTR_ENTRY_DELAY_HOME): vol.All(
            cv.time_period,
            lambda value: value.total_seconds(),
            vol.Range(max=MAX_ENTRY_DELAY_HOME),
        ),
        vol.Optional(ATTR_EXIT_DELAY_AWAY): vol.All(
            cv.time_period,
            lambda value: value.total_seconds(),
            vol.Range(min=MIN_EXIT_DELAY_AWAY, max=MAX_EXIT_DELAY_AWAY),
        ),
        vol.Optional(ATTR_EXIT_DELAY_HOME): vol.All(
            cv.time_period,
            lambda value: value.total_seconds(),
            vol.Range(max=MAX_EXIT_DELAY_HOME),
        ),
        vol.Optional(ATTR_LIGHT): cv.boolean,
        vol.Optional(ATTR_VOICE_PROMPT_VOLUME): vol.All(
            vol.In(VOLUME_MAP), VOLUME_MAP.get
        ),
    }
)

WEBSOCKET_EVENTS_REQUIRING_SERIAL = [EVENT_LOCK_LOCKED, EVENT_LOCK_UNLOCKED]
WEBSOCKET_EVENTS_TO_FIRE_HASS_EVENT = [
    EVENT_AUTOMATIC_TEST,
    EVENT_CAMERA_MOTION_DETECTED,
    EVENT_DOORBELL_DETECTED,
    EVENT_DEVICE_TEST,
    EVENT_SECRET_ALERT_TRIGGERED,
    EVENT_SENSOR_PAIRED_AND_NAMED,
    EVENT_USER_INITIATED_TEST,
]

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


@callback
def _async_get_system_for_service_call(
    hass: HomeAssistant, call: ServiceCall
) -> SystemType:
    """Get the SimpliSafe system related to a service call (by device ID)."""
    device_id = call.data[ATTR_DEVICE_ID]
    device_registry = dr.async_get(hass)

    if (
        alarm_control_panel_device_entry := device_registry.async_get(device_id)
    ) is None:
        raise vol.Invalid("Invalid device ID specified")

    assert alarm_control_panel_device_entry.via_device_id

    if (
        base_station_device_entry := device_registry.async_get(
            alarm_control_panel_device_entry.via_device_id
        )
    ) is None:
        raise ValueError("No base station registered for alarm control panel")

    [system_id_str] = [
        identity[1]
        for identity in base_station_device_entry.identifiers
        if identity[0] == DOMAIN
    ]
    system_id = int(system_id_str)

    for entry_id in base_station_device_entry.config_entries:
        if (simplisafe := hass.data[DOMAIN].get(entry_id)) is None:
            continue
        return cast(SystemType, simplisafe.systems[system_id])

    raise ValueError(f"No system for device ID: {device_id}")


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
        model=system.version,
        name=system.address,
    )

    # Check for an old system ID format and remove it:
    if old_base_station := device_registry.async_get_device(
        identifiers={(DOMAIN, system.system_id)}  # type: ignore[arg-type]
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SimpliSafe as config entry."""
    _async_standardize_config_entry(hass, entry)

    _verify_domain_control = verify_domain_control(hass, DOMAIN)
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

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = simplisafe

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def extract_system(func: Callable) -> Callable:
        """Define a decorator to get the correct system for a service call."""

        async def wrapper(call: ServiceCall) -> None:
            """Wrap the service function."""
            system = _async_get_system_for_service_call(hass, call)

            try:
                await func(call, system)
            except SimplipyError as err:
                raise HomeAssistantError(
                    f'Error while executing "{call.service}": {err}'
                ) from err

        return wrapper

    @_verify_domain_control
    @extract_system
    async def async_remove_pin(call: ServiceCall, system: SystemType) -> None:
        """Remove a PIN."""
        await system.async_remove_pin(call.data[ATTR_PIN_LABEL_OR_VALUE])

    @_verify_domain_control
    @extract_system
    async def async_set_pin(call: ServiceCall, system: SystemType) -> None:
        """Set a PIN."""
        await system.async_set_pin(call.data[ATTR_PIN_LABEL], call.data[ATTR_PIN_VALUE])

    @_verify_domain_control
    @extract_system
    async def async_set_system_properties(
        call: ServiceCall, system: SystemType
    ) -> None:
        """Set one or more system parameters."""
        if not isinstance(system, SystemV3):
            raise HomeAssistantError("Can only set system properties on V3 systems")

        await system.async_set_properties(
            {prop: value for prop, value in call.data.items() if prop != ATTR_DEVICE_ID}
        )

    for service, method, schema in (
        (SERVICE_NAME_REMOVE_PIN, async_remove_pin, SERVICE_REMOVE_PIN_SCHEMA),
        (SERVICE_NAME_SET_PIN, async_set_pin, SERVICE_SET_PIN_SCHEMA),
        (
            SERVICE_NAME_SET_SYSTEM_PROPERTIES,
            async_set_system_properties,
            SERVICE_SET_SYSTEM_PROPERTIES_SCHEMA,
        ),
    ):
        if hass.services.has_service(DOMAIN, service):
            continue
        async_register_admin_service(hass, DOMAIN, service, method, schema=schema)

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


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a SimpliSafe config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    loaded_entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state == ConfigEntryState.LOADED
    ]
    if len(loaded_entries) == 1:
        # If this is the last loaded instance of SimpliSafe, deregister any services
        # defined during integration setup:
        for service_name in SERVICES:
            hass.services.async_remove(DOMAIN, service_name)

    return unload_ok


class SimpliSafe:
    """Define a SimpliSafe data object."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: API) -> None:
        """Initialize."""
        self._api = api
        self._hass = hass
        self._system_notifications: dict[int, set[SystemNotification]] = {}
        self._websocket_reconnect_task: asyncio.Task | None = None
        self.entry = entry
        self.initial_event_to_use: dict[int, dict[str, Any]] = {}
        self.subscription_data: dict[int, Any] = api.subscription_data
        self.systems: dict[int, SystemType] = {}

        # This will get filled in by async_init:
        self.coordinator: DataUpdateCoordinator[None] | None = None

    @callback
    def _async_process_new_notifications(self, system: SystemType) -> None:
        """Act on any new system notifications."""
        if self._hass.state != CoreState.running:
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

    async def _async_start_websocket_loop(self) -> None:
        """Start a websocket reconnection loop."""
        assert self._api.websocket

        try:
            await self._api.websocket.async_connect()
            await self._api.websocket.async_listen()
        except asyncio.CancelledError:
            LOGGER.debug("Request to cancel websocket loop received")
            raise
        except WebsocketError as err:
            LOGGER.error("Failed to connect to websocket: %s", err)
        except Exception as err:  # pylint: disable=broad-except
            LOGGER.error("Unknown exception while connecting to websocket: %s", err)

        LOGGER.info("Reconnecting to websocket")
        await self._async_cancel_websocket_loop()
        self._websocket_reconnect_task = self._hass.async_create_task(
            self._async_start_websocket_loop()
        )

    async def _async_cancel_websocket_loop(self) -> None:
        """Stop any existing websocket reconnection loop."""
        if self._websocket_reconnect_task:
            self._websocket_reconnect_task.cancel()
            try:
                await self._websocket_reconnect_task
            except asyncio.CancelledError:
                LOGGER.debug("Websocket reconnection task successfully canceled")
                self._websocket_reconnect_task = None

            assert self._api.websocket
            await self._api.websocket.async_disconnect()

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
        self._websocket_reconnect_task = asyncio.create_task(
            self._async_start_websocket_loop()
        )

        async def async_websocket_disconnect_listener(_: Event) -> None:
            """Define an event handler to disconnect from the websocket."""
            assert self._api.websocket
            await self._async_cancel_websocket_loop()

        self.entry.async_on_unload(
            self._hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, async_websocket_disconnect_listener
            )
        )

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

        self.coordinator = DataUpdateCoordinator(
            self._hass,
            LOGGER,
            name=self.entry.title,
            update_interval=DEFAULT_SCAN_INTERVAL,
            update_method=self.async_update,
        )

        @callback
        def async_save_refresh_token(token: str) -> None:
            """Save a refresh token to the config entry."""
            LOGGER.info("Saving new refresh token to HASS storage")
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
            self._websocket_reconnect_task = self._hass.async_create_task(
                self._async_start_websocket_loop()
            )

        self.entry.async_on_unload(
            self._api.add_refresh_token_callback(async_handle_refresh_token)
        )

        # Save the refresh token we got on entry setup:
        async_save_refresh_token(self._api.refresh_token)

    async def async_update(self) -> None:
        """Get updated data from SimpliSafe."""

        async def async_update_system(system: SystemType) -> None:
            """Update a system."""
            await system.async_update(cached=system.version != 3)
            self._async_process_new_notifications(system)

        tasks = [async_update_system(system) for system in self.systems.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, InvalidCredentialsError):
                raise ConfigEntryAuthFailed("Invalid credentials") from result

            if isinstance(result, EndpointUnavailableError):
                # In case the user attempts an action not allowed in their current plan,
                # we merely log that message at INFO level (so the user is aware,
                # but not spammed with ERROR messages that they cannot change):
                LOGGER.info(result)

            if isinstance(result, SimplipyError):
                raise UpdateFailed(f"SimpliSafe error while updating: {result}")


class SimpliSafeEntity(CoordinatorEntity[DataUpdateCoordinator[None]]):
    """Define a base SimpliSafe entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        simplisafe: SimpliSafe,
        system: SystemType,
        *,
        device: Device | None = None,
        additional_websocket_events: Iterable[str] | None = None,
    ) -> None:
        """Initialize."""
        assert simplisafe.coordinator
        super().__init__(simplisafe.coordinator)

        # SimpliSafe can incorrectly return an error state when there isn't any
        # error. This can lead to entities having an unknown state frequently.
        # To protect against that, we measure an error count for each entity and only
        # mark the state as unavailable if we detect a few in a row:
        self._error_count = 0

        if device:
            model = device.type.name.capitalize().replace("_", " ")
            device_name = f"{device.name.capitalize()} {model}"
            serial = device.serial
        else:
            model = device_name = DEFAULT_ENTITY_MODEL
            serial = system.serial

        event = simplisafe.initial_event_to_use[system.system_id]

        if raw_type := event.get("sensorType"):
            try:
                device_type = DeviceTypes(raw_type)
            except ValueError:
                device_type = DeviceTypes.UNKNOWN
        else:
            device_type = DeviceTypes.UNKNOWN

        self._attr_extra_state_attributes = {
            ATTR_LAST_EVENT_INFO: event.get("info"),
            ATTR_LAST_EVENT_SENSOR_NAME: event.get("sensorName"),
            ATTR_LAST_EVENT_SENSOR_TYPE: device_type.name.lower(),
            ATTR_LAST_EVENT_TIMESTAMP: event.get("eventTimestamp"),
            ATTR_SYSTEM_ID: system.system_id,
        }

        self._attr_device_info = DeviceInfo(
            configuration_url=DEFAULT_CONFIG_URL,
            identifiers={(DOMAIN, serial)},
            manufacturer="SimpliSafe",
            model=model,
            name=device_name,
            via_device=(DOMAIN, str(system.system_id)),
        )

        self._attr_unique_id = serial
        self._device = device
        self._online = True
        self._simplisafe = simplisafe
        self._system = system
        self._websocket_events_to_listen_for = [
            EVENT_CONNECTION_LOST,
            EVENT_CONNECTION_RESTORED,
            EVENT_POWER_OUTAGE,
            EVENT_POWER_RESTORED,
        ]
        if additional_websocket_events:
            self._websocket_events_to_listen_for += additional_websocket_events

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        # We can easily detect if the V3 system is offline, but no simple check exists
        # for the V2 system. Therefore, assuming the coordinator hasn't failed, we mark
        # the entity as available if:
        #   1. We can verify that the system is online (assuming True if we can't)
        #   2. We can verify that the entity is online
        if isinstance(self._system, SystemV3):
            system_offline = self._system.offline
        else:
            system_offline = False

        return (
            self._error_count < DEFAULT_ERROR_THRESHOLD
            and self._online
            and not system_offline
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the entity with new REST API data."""
        if self.coordinator.last_update_success:
            self.async_reset_error_count()
        else:
            self.async_increment_error_count()

        self.async_update_from_rest_api()
        self.async_write_ha_state()

    @callback
    def _handle_websocket_update(self, event: WebsocketEvent) -> None:
        """Update the entity with new websocket data."""
        # Ignore this event if it belongs to a system other than this one:
        if event.system_id != self._system.system_id:
            return

        # Ignore this event if this entity hasn't expressed interest in its type:
        if event.event_type not in self._websocket_events_to_listen_for:
            return

        # Ignore this event if it belongs to a entity with a different serial
        # number from this one's:
        if (
            self._device
            and event.event_type in WEBSOCKET_EVENTS_REQUIRING_SERIAL
            and event.sensor_serial != self._device.serial
        ):
            return

        sensor_type: str | None
        if event.sensor_type:
            sensor_type = event.sensor_type.name
        else:
            sensor_type = None

        self._attr_extra_state_attributes.update(
            {
                ATTR_LAST_EVENT_INFO: event.info,
                ATTR_LAST_EVENT_SENSOR_NAME: event.sensor_name,
                ATTR_LAST_EVENT_SENSOR_TYPE: sensor_type,
                ATTR_LAST_EVENT_TIMESTAMP: event.timestamp,
            }
        )

        # It's unknown whether these events reach the base station (since the connection
        # is lost); we include this for completeness and coverage:
        if event.event_type in (EVENT_CONNECTION_LOST, EVENT_POWER_OUTAGE):
            self._online = False
            return

        # If the base station comes back online, set entities to available, but don't
        # instruct the entities to update their state (since there won't be anything new
        # until the next websocket event or REST API update:
        if event.event_type in (EVENT_CONNECTION_RESTORED, EVENT_POWER_RESTORED):
            self._online = True
            return

        self.async_update_from_websocket_event(event)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                DISPATCHER_TOPIC_WEBSOCKET_EVENT.format(self._system.system_id),
                self._handle_websocket_update,
            )
        )

        self.async_update_from_rest_api()

    @callback
    def async_increment_error_count(self) -> None:
        """Increment this entity's error count."""
        LOGGER.debug('Error for entity "%s" (total: %s)', self.name, self._error_count)
        self._error_count += 1

    @callback
    def async_reset_error_count(self) -> None:
        """Reset this entity's error count."""
        if self._error_count == 0:
            return

        LOGGER.debug('Resetting error count for "%s"', self.name)
        self._error_count = 0

    @callback
    def async_update_from_rest_api(self) -> None:
        """Update the entity when new data comes from the REST API."""

    @callback
    def async_update_from_websocket_event(self, event: WebsocketEvent) -> None:
        """Update the entity when new data comes from the websocket."""
