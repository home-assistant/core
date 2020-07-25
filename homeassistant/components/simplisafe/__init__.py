"""Support for SimpliSafe alarm systems."""
import asyncio
import logging

from simplipy import API
from simplipy.errors import InvalidCredentialsError, SimplipyError
from simplipy.websocket import (
    EVENT_CAMERA_MOTION_DETECTED,
    EVENT_CONNECTION_LOST,
    EVENT_CONNECTION_RESTORED,
    EVENT_DOORBELL_DETECTED,
    EVENT_ENTRY_DETECTED,
    EVENT_LOCK_LOCKED,
    EVENT_LOCK_UNLOCKED,
    EVENT_MOTION_DETECTED,
)
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_CODE,
    CONF_CODE,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import CoreState, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    aiohttp_client,
    config_validation as cv,
    device_registry as dr,
)
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.service import (
    async_register_admin_service,
    verify_domain_control,
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
    DATA_CLIENT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    VOLUMES,
)

_LOGGER = logging.getLogger(__name__)

CONF_ACCOUNTS = "accounts"

DATA_LISTENER = "listener"
TOPIC_UPDATE_REST_API = "simplisafe_update_rest_api_{0}"
TOPIC_UPDATE_WEBSOCKET = "simplisafe_update_websocket_{0}"

EVENT_SIMPLISAFE_EVENT = "SIMPLISAFE_EVENT"
EVENT_SIMPLISAFE_NOTIFICATION = "SIMPLISAFE_NOTIFICATION"

DEFAULT_SOCKET_MIN_RETRY = 15

WEBSOCKET_EVENTS_REQUIRING_SERIAL = [EVENT_LOCK_LOCKED, EVENT_LOCK_UNLOCKED]
WEBSOCKET_EVENTS_TO_TRIGGER_HASS_EVENT = [
    EVENT_CAMERA_MOTION_DETECTED,
    EVENT_DOORBELL_DETECTED,
    EVENT_ENTRY_DETECTED,
    EVENT_MOTION_DETECTED,
]

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

SERVICE_BASE_SCHEMA = vol.Schema({vol.Required(ATTR_SYSTEM_ID): cv.positive_int})

SERVICE_REMOVE_PIN_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {vol.Required(ATTR_PIN_LABEL_OR_VALUE): cv.string}
)

SERVICE_SET_PIN_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {vol.Required(ATTR_PIN_LABEL): cv.string, vol.Required(ATTR_PIN_VALUE): cv.string}
)

SERVICE_SET_SYSTEM_PROPERTIES_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {
        vol.Optional(ATTR_ALARM_DURATION): vol.All(
            cv.time_period, lambda value: value.seconds, vol.Range(min=30, max=480)
        ),
        vol.Optional(ATTR_ALARM_VOLUME): vol.All(vol.Coerce(int), vol.In(VOLUMES)),
        vol.Optional(ATTR_CHIME_VOLUME): vol.All(vol.Coerce(int), vol.In(VOLUMES)),
        vol.Optional(ATTR_ENTRY_DELAY_AWAY): vol.All(
            cv.time_period, lambda value: value.seconds, vol.Range(min=30, max=255)
        ),
        vol.Optional(ATTR_ENTRY_DELAY_HOME): vol.All(
            cv.time_period, lambda value: value.seconds, vol.Range(max=255)
        ),
        vol.Optional(ATTR_EXIT_DELAY_AWAY): vol.All(
            cv.time_period, lambda value: value.seconds, vol.Range(min=45, max=255)
        ),
        vol.Optional(ATTR_EXIT_DELAY_HOME): vol.All(
            cv.time_period, lambda value: value.seconds, vol.Range(max=255)
        ),
        vol.Optional(ATTR_LIGHT): cv.boolean,
        vol.Optional(ATTR_VOICE_PROMPT_VOLUME): vol.All(
            vol.Coerce(int), vol.In(VOLUMES)
        ),
    }
)

ACCOUNT_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_CODE): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_ACCOUNTS): vol.All(
                    cv.ensure_list, [ACCOUNT_CONFIG_SCHEMA]
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


@callback
def _async_save_refresh_token(hass, config_entry, token):
    """Save a refresh token to the config entry."""
    hass.config_entries.async_update_entry(
        config_entry, data={**config_entry.data, CONF_TOKEN: token}
    )


async def async_register_base_station(hass, system, config_entry_id):
    """Register a new bridge."""
    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry_id,
        identifiers={(DOMAIN, system.serial)},
        manufacturer="SimpliSafe",
        model=system.version,
        name=system.address,
    )


async def async_setup(hass, config):
    """Set up the SimpliSafe component."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_CLIENT] = {}
    hass.data[DOMAIN][DATA_LISTENER] = {}

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    for account in conf[CONF_ACCOUNTS]:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={
                    CONF_USERNAME: account[CONF_USERNAME],
                    CONF_PASSWORD: account[CONF_PASSWORD],
                    CONF_CODE: account.get(CONF_CODE),
                },
            )
        )

    return True


async def async_setup_entry(hass, config_entry):
    """Set up SimpliSafe as config entry."""
    entry_updates = {}
    if not config_entry.unique_id:
        # If the config entry doesn't already have a unique ID, set one:
        entry_updates["unique_id"] = config_entry.data[CONF_USERNAME]
    if CONF_CODE in config_entry.data:
        # If an alarm code was provided as part of configuration.yaml, pop it out of
        # the config entry's data and move it to options:
        data = {**config_entry.data}
        entry_updates["data"] = data
        entry_updates["options"] = {
            **config_entry.options,
            CONF_CODE: data.pop(CONF_CODE),
        }
    if entry_updates:
        hass.config_entries.async_update_entry(config_entry, **entry_updates)

    _verify_domain_control = verify_domain_control(hass, DOMAIN)

    websession = aiohttp_client.async_get_clientsession(hass)

    try:
        api = await API.login_via_token(
            config_entry.data[CONF_TOKEN], session=websession
        )
    except InvalidCredentialsError:
        _LOGGER.error("Invalid credentials provided")
        return False
    except SimplipyError as err:
        _LOGGER.error("Config entry failed: %s", err)
        raise ConfigEntryNotReady

    _async_save_refresh_token(hass, config_entry, api.refresh_token)

    simplisafe = SimpliSafe(hass, api, config_entry)
    await simplisafe.async_init()
    hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id] = simplisafe

    for component in ("alarm_control_panel", "lock"):
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    @callback
    def verify_system_exists(coro):
        """Log an error if a service call uses an invalid system ID."""

        async def decorator(call):
            """Decorate."""
            system_id = int(call.data[ATTR_SYSTEM_ID])
            if system_id not in simplisafe.systems:
                _LOGGER.error("Unknown system ID in service call: %s", system_id)
                return
            await coro(call)

        return decorator

    @callback
    def v3_only(coro):
        """Log an error if the decorated coroutine is called with a v2 system."""

        async def decorator(call):
            """Decorate."""
            system = simplisafe.systems[int(call.data[ATTR_SYSTEM_ID])]
            if system.version != 3:
                _LOGGER.error("Service only available on V3 systems")
                return
            await coro(call)

        return decorator

    @verify_system_exists
    @_verify_domain_control
    async def clear_notifications(call):
        """Clear all active notifications."""
        system = simplisafe.systems[call.data[ATTR_SYSTEM_ID]]
        try:
            await system.clear_notifications()
        except SimplipyError as err:
            _LOGGER.error("Error during service call: %s", err)
            return

    @verify_system_exists
    @_verify_domain_control
    async def remove_pin(call):
        """Remove a PIN."""
        system = simplisafe.systems[call.data[ATTR_SYSTEM_ID]]
        try:
            await system.remove_pin(call.data[ATTR_PIN_LABEL_OR_VALUE])
        except SimplipyError as err:
            _LOGGER.error("Error during service call: %s", err)
            return

    @verify_system_exists
    @_verify_domain_control
    async def set_pin(call):
        """Set a PIN."""
        system = simplisafe.systems[call.data[ATTR_SYSTEM_ID]]
        try:
            await system.set_pin(call.data[ATTR_PIN_LABEL], call.data[ATTR_PIN_VALUE])
        except SimplipyError as err:
            _LOGGER.error("Error during service call: %s", err)
            return

    @verify_system_exists
    @v3_only
    @_verify_domain_control
    async def set_system_properties(call):
        """Set one or more system parameters."""
        system = simplisafe.systems[call.data[ATTR_SYSTEM_ID]]
        try:
            await system.set_properties(
                {
                    prop: value
                    for prop, value in call.data.items()
                    if prop != ATTR_SYSTEM_ID
                }
            )
        except SimplipyError as err:
            _LOGGER.error("Error during service call: %s", err)
            return

    for service, method, schema in [
        ("clear_notifications", clear_notifications, None),
        ("remove_pin", remove_pin, SERVICE_REMOVE_PIN_SCHEMA),
        ("set_pin", set_pin, SERVICE_SET_PIN_SCHEMA),
        (
            "set_system_properties",
            set_system_properties,
            SERVICE_SET_SYSTEM_PROPERTIES_SCHEMA,
        ),
    ]:
        async_register_admin_service(hass, DOMAIN, service, method, schema=schema)

    config_entry.add_update_listener(async_update_options)

    return True


async def async_unload_entry(hass, entry):
    """Unload a SimpliSafe config entry."""
    tasks = [
        hass.config_entries.async_forward_entry_unload(entry, component)
        for component in ("alarm_control_panel", "lock")
    ]

    await asyncio.gather(*tasks)

    hass.data[DOMAIN][DATA_CLIENT].pop(entry.entry_id)
    remove_listener = hass.data[DOMAIN][DATA_LISTENER].pop(entry.entry_id)
    remove_listener()

    return True


async def async_update_options(hass, config_entry):
    """Handle an options update."""
    simplisafe = hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id]
    simplisafe.options = config_entry.options


class SimpliSafeWebsocket:
    """Define a SimpliSafe websocket "manager" object."""

    def __init__(self, hass, websocket):
        """Initialize."""
        self._hass = hass
        self._websocket = websocket

    @staticmethod
    def _on_connect():
        """Define a handler to fire when the websocket is connected."""
        _LOGGER.info("Connected to websocket")

    @staticmethod
    def _on_disconnect():
        """Define a handler to fire when the websocket is disconnected."""
        _LOGGER.info("Disconnected from websocket")

    def _on_event(self, event):
        """Define a handler to fire when a new SimpliSafe event arrives."""
        _LOGGER.debug("New websocket event: %s", event)
        async_dispatcher_send(
            self._hass, TOPIC_UPDATE_WEBSOCKET.format(event.system_id), event
        )

        if event.event_type not in WEBSOCKET_EVENTS_TO_TRIGGER_HASS_EVENT:
            return

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

    async def async_websocket_connect(self):
        """Register handlers and connect to the websocket."""
        self._websocket.on_connect(self._on_connect)
        self._websocket.on_disconnect(self._on_disconnect)
        self._websocket.on_event(self._on_event)

        await self._websocket.async_connect()


class SimpliSafe:
    """Define a SimpliSafe data object."""

    def __init__(self, hass, api, config_entry):
        """Initialize."""
        self._api = api
        self._config_entry = config_entry
        self._emergency_refresh_token_used = False
        self._hass = hass
        self._system_notifications = {}
        self.options = config_entry.options or {}
        self.initial_event_to_use = {}
        self.systems = {}
        self.websocket = SimpliSafeWebsocket(hass, api.websocket)

    @callback
    def _async_process_new_notifications(self, system):
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

        _LOGGER.debug("New system notifications: %s", to_add)

        self._system_notifications[system.system_id].update(to_add)

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

    async def async_init(self):
        """Initialize the data class."""
        asyncio.create_task(self.websocket.async_websocket_connect())

        self.systems = await self._api.get_systems()
        for system in self.systems.values():
            self._system_notifications[system.system_id] = set()

            self._hass.async_create_task(
                async_register_base_station(
                    self._hass, system, self._config_entry.entry_id
                )
            )

            # Future events will come from the websocket, but since subscription to the
            # websocket doesn't provide the most recent event, we grab it from the REST
            # API to ensure event-related attributes aren't empty on startup:
            try:
                self.initial_event_to_use[
                    system.system_id
                ] = await system.get_latest_event()
            except SimplipyError as err:
                _LOGGER.error("Error while fetching initial event: %s", err)
                self.initial_event_to_use[system.system_id] = {}

        async def refresh(event_time):
            """Refresh data from the SimpliSafe account."""
            await self.async_update()

        self._hass.data[DOMAIN][DATA_LISTENER][
            self._config_entry.entry_id
        ] = async_track_time_interval(self._hass, refresh, DEFAULT_SCAN_INTERVAL)

        await self.async_update()

    async def async_update(self):
        """Get updated data from SimpliSafe."""

        async def update_system(system):
            """Update a system."""
            await system.update()
            self._async_process_new_notifications(system)
            _LOGGER.debug('Updated REST API data for "%s"', system.address)
            async_dispatcher_send(
                self._hass, TOPIC_UPDATE_REST_API.format(system.system_id)
            )

        tasks = [update_system(system) for system in self.systems.values()]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, InvalidCredentialsError):
                if self._emergency_refresh_token_used:
                    _LOGGER.error(
                        "SimpliSafe authentication disconnected. Please restart HASS"
                    )
                    remove_listener = self._hass.data[DOMAIN][DATA_LISTENER].pop(
                        self._config_entry.entry_id
                    )
                    remove_listener()
                    return

                _LOGGER.warning("SimpliSafe cloud error; trying stored refresh token")
                self._emergency_refresh_token_used = True
                return await self._api.refresh_access_token(
                    self._config_entry.data[CONF_TOKEN]
                )

            if isinstance(result, SimplipyError):
                _LOGGER.error("SimpliSafe error while updating: %s", result)
                return

            if isinstance(result, SimplipyError):
                _LOGGER.error("Unknown error while updating: %s", result)
                return

        if self._api.refresh_token != self._config_entry.data[CONF_TOKEN]:
            _async_save_refresh_token(
                self._hass, self._config_entry, self._api.refresh_token
            )

        # If we've reached this point using an emergency refresh token, we're in the
        # clear and we can discard it:
        if self._emergency_refresh_token_used:
            self._emergency_refresh_token_used = False


class SimpliSafeEntity(Entity):
    """Define a base SimpliSafe entity."""

    def __init__(self, simplisafe, system, name, *, serial=None):
        """Initialize."""
        self._name = name
        self._online = True
        self._simplisafe = simplisafe
        self._system = system
        self.websocket_events_to_listen_for = [
            EVENT_CONNECTION_LOST,
            EVENT_CONNECTION_RESTORED,
        ]

        if serial:
            self._serial = serial
        else:
            self._serial = system.serial

        self._attrs = {
            ATTR_LAST_EVENT_INFO: simplisafe.initial_event_to_use[system.system_id].get(
                "info"
            ),
            ATTR_LAST_EVENT_SENSOR_NAME: simplisafe.initial_event_to_use[
                system.system_id
            ].get("sensorName"),
            ATTR_LAST_EVENT_SENSOR_TYPE: simplisafe.initial_event_to_use[
                system.system_id
            ].get("sensorType"),
            ATTR_LAST_EVENT_TIMESTAMP: simplisafe.initial_event_to_use[
                system.system_id
            ].get("eventTimestamp"),
            ATTR_SYSTEM_ID: system.system_id,
        }

    @property
    def available(self):
        """Return whether the entity is available."""
        # We can easily detect if the V3 system is offline, but no simple check exists
        # for the V2 system. Therefore, we mark the entity as available if:
        #   1. We can verify that the system is online (assuming True if we can't)
        #   2. We can verify that the entity is online
        system_offline = self._system.version == 3 and self._system.offline
        return not system_offline and self._online

    @property
    def device_info(self):
        """Return device registry information for this entity."""
        return {
            "identifiers": {(DOMAIN, self._system.system_id)},
            "manufacturer": "SimpliSafe",
            "model": self._system.version,
            "name": self._name,
            "via_device": (DOMAIN, self._system.serial),
        }

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    @property
    def name(self):
        """Return the name of the entity."""
        return f"{self._system.address} {self._name}"

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return self._serial

    @callback
    def _async_internal_update_from_websocket_event(self, event):
        """Perform internal websocket handling prior to handing off."""
        if event.event_type == EVENT_CONNECTION_LOST:
            self._online = False
        elif event.event_type == EVENT_CONNECTION_RESTORED:
            self._online = True

        # It's uncertain whether SimpliSafe events will still propagate down the
        # websocket when the base station is offline. Just in case, we guard against
        # further action until connection is restored:
        if not self._online:
            return

        if event.sensor_type:
            sensor_type = event.sensor_type.name
        else:
            sensor_type = None

        self._attrs.update(
            {
                ATTR_LAST_EVENT_INFO: event.info,
                ATTR_LAST_EVENT_SENSOR_NAME: event.sensor_name,
                ATTR_LAST_EVENT_SENSOR_TYPE: sensor_type,
                ATTR_LAST_EVENT_TIMESTAMP: event.timestamp,
            }
        )

        self.async_update_from_websocket_event(event)

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def rest_api_update():
            """Update the entity with new REST API data."""
            self.async_update_from_rest_api()
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                TOPIC_UPDATE_REST_API.format(self._system.system_id),
                rest_api_update,
            )
        )

        @callback
        def websocket_update(event):
            """Update the entity with new websocket data."""
            # Ignore this event if it belongs to a system other than this one:
            if event.system_id != self._system.system_id:
                return

            # Ignore this event if this entity hasn't expressed interest in its type:
            if event.event_type not in self.websocket_events_to_listen_for:
                return

            # Ignore this event if it belongs to a entity with a different serial
            # number from this one's:
            if (
                event.event_type in WEBSOCKET_EVENTS_REQUIRING_SERIAL
                and event.sensor_serial != self._serial
            ):
                return

            self._async_internal_update_from_websocket_event(event)
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                TOPIC_UPDATE_WEBSOCKET.format(self._system.system_id),
                websocket_update,
            )
        )

        self.async_update_from_rest_api()

    @callback
    def async_update_from_rest_api(self):
        """Update the entity with the provided REST API data."""
        raise NotImplementedError()

    @callback
    def async_update_from_websocket_event(self, event):
        """Update the entity with the provided websocket event."""
        raise NotImplementedError()
