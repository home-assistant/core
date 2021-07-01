"""Support for SimpliSafe alarm systems."""
import asyncio
from uuid import UUID

from simplipy import API
from simplipy.errors import EndpointUnavailable, InvalidCredentialsError, SimplipyError
import voluptuous as vol

from homeassistant.const import ATTR_CODE, CONF_CODE, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import CoreState, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    aiohttp_client,
    config_validation as cv,
    device_registry as dr,
)
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
    DATA_CLIENT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
    VOLUMES,
)

DATA_LISTENER = "listener"

EVENT_SIMPLISAFE_NOTIFICATION = "SIMPLISAFE_NOTIFICATION"

DEFAULT_SOCKET_MIN_RETRY = 15

PLATFORMS = (
    "alarm_control_panel",
    "binary_sensor",
    "lock",
    "sensor",
)

ATTR_CATEGORY = "category"
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
            cv.time_period,
            lambda value: value.total_seconds(),
            vol.Range(min=30, max=480),
        ),
        vol.Optional(ATTR_ALARM_VOLUME): vol.All(vol.Coerce(int), vol.In(VOLUMES)),
        vol.Optional(ATTR_CHIME_VOLUME): vol.All(vol.Coerce(int), vol.In(VOLUMES)),
        vol.Optional(ATTR_ENTRY_DELAY_AWAY): vol.All(
            cv.time_period,
            lambda value: value.total_seconds(),
            vol.Range(min=30, max=255),
        ),
        vol.Optional(ATTR_ENTRY_DELAY_HOME): vol.All(
            cv.time_period, lambda value: value.total_seconds(), vol.Range(max=255)
        ),
        vol.Optional(ATTR_EXIT_DELAY_AWAY): vol.All(
            cv.time_period,
            lambda value: value.total_seconds(),
            vol.Range(min=45, max=255),
        ),
        vol.Optional(ATTR_EXIT_DELAY_HOME): vol.All(
            cv.time_period, lambda value: value.total_seconds(), vol.Range(max=255)
        ),
        vol.Optional(ATTR_LIGHT): cv.boolean,
        vol.Optional(ATTR_VOICE_PROMPT_VOLUME): vol.All(
            vol.Coerce(int), vol.In(VOLUMES)
        ),
    }
)

CONFIG_SCHEMA = cv.deprecated(DOMAIN)


async def async_get_client_id(hass):
    """Get a client ID (based on the HASS unique ID) for the SimpliSafe API.

    Note that SimpliSafe requires full, "dashed" versions of UUIDs.
    """
    hass_id = await hass.helpers.instance_id.async_get()
    return str(UUID(hass_id))


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


async def async_setup_entry(hass, config_entry):  # noqa: C901
    """Set up SimpliSafe as config entry."""
    hass.data.setdefault(DOMAIN, {DATA_CLIENT: {}, DATA_LISTENER: {}})
    hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id] = []
    hass.data[DOMAIN][DATA_LISTENER][config_entry.entry_id] = []

    if CONF_PASSWORD not in config_entry.data:
        raise ConfigEntryAuthFailed("Config schema change requires re-authentication")

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

    client_id = await async_get_client_id(hass)
    websession = aiohttp_client.async_get_clientsession(hass)

    async def async_get_api():
        """Define a helper to get an authenticated SimpliSafe API object."""
        return await API.login_via_credentials(
            config_entry.data[CONF_USERNAME],
            config_entry.data[CONF_PASSWORD],
            client_id=client_id,
            session=websession,
        )

    try:
        api = await async_get_api()
    except InvalidCredentialsError as err:
        raise ConfigEntryAuthFailed from err
    except SimplipyError as err:
        LOGGER.error("Config entry failed: %s", err)
        raise ConfigEntryNotReady from err

    simplisafe = SimpliSafe(hass, config_entry, api, async_get_api)

    try:
        await simplisafe.async_init()
    except SimplipyError as err:
        raise ConfigEntryNotReady from err

    hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id] = simplisafe
    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    @callback
    def verify_system_exists(coro):
        """Log an error if a service call uses an invalid system ID."""

        async def decorator(call):
            """Decorate."""
            system_id = int(call.data[ATTR_SYSTEM_ID])
            if system_id not in simplisafe.systems:
                LOGGER.error("Unknown system ID in service call: %s", system_id)
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
                LOGGER.error("Service only available on V3 systems")
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
            LOGGER.error("Error during service call: %s", err)
            return

    @verify_system_exists
    @_verify_domain_control
    async def remove_pin(call):
        """Remove a PIN."""
        system = simplisafe.systems[call.data[ATTR_SYSTEM_ID]]
        try:
            await system.remove_pin(call.data[ATTR_PIN_LABEL_OR_VALUE])
        except SimplipyError as err:
            LOGGER.error("Error during service call: %s", err)
            return

    @verify_system_exists
    @_verify_domain_control
    async def set_pin(call):
        """Set a PIN."""
        system = simplisafe.systems[call.data[ATTR_SYSTEM_ID]]
        try:
            await system.set_pin(call.data[ATTR_PIN_LABEL], call.data[ATTR_PIN_VALUE])
        except SimplipyError as err:
            LOGGER.error("Error during service call: %s", err)
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
            LOGGER.error("Error during service call: %s", err)
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

    hass.data[DOMAIN][DATA_LISTENER][config_entry.entry_id].append(
        config_entry.add_update_listener(async_reload_entry)
    )

    return True


async def async_unload_entry(hass, entry):
    """Unload a SimpliSafe config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN][DATA_CLIENT].pop(entry.entry_id)
        for remove_listener in hass.data[DOMAIN][DATA_LISTENER].pop(entry.entry_id):
            remove_listener()

    return unload_ok


async def async_reload_entry(hass, config_entry):
    """Handle an options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


class SimpliSafe:
    """Define a SimpliSafe data object."""

    def __init__(self, hass, config_entry, api, async_get_api):
        """Initialize."""
        self._api = api
        self._async_get_api = async_get_api
        self._hass = hass
        self._system_notifications = {}
        self.config_entry = config_entry
        self.coordinator = None
        self.systems = {}

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

        LOGGER.debug("New system notifications: %s", to_add)

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
        self.systems = await self._api.get_systems()
        for system in self.systems.values():
            self._system_notifications[system.system_id] = set()

            self._hass.async_create_task(
                async_register_base_station(
                    self._hass, system, self.config_entry.entry_id
                )
            )

        self.coordinator = DataUpdateCoordinator(
            self._hass,
            LOGGER,
            name=self.config_entry.data[CONF_USERNAME],
            update_interval=DEFAULT_SCAN_INTERVAL,
            update_method=self.async_update,
        )

    async def async_update(self):
        """Get updated data from SimpliSafe."""

        async def async_update_system(system):
            """Update a system."""
            await system.update(cached=system.version != 3)
            self._async_process_new_notifications(system)

        tasks = [async_update_system(system) for system in self.systems.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, InvalidCredentialsError):
                try:
                    self._api = await self._async_get_api()
                    return
                except InvalidCredentialsError as err:
                    raise ConfigEntryAuthFailed(
                        "Unable to re-authenticate with SimpliSafe"
                    ) from err
                except SimplipyError as err:
                    raise UpdateFailed(
                        f"SimpliSafe error while updating: {err}"
                    ) from err

            if isinstance(result, EndpointUnavailable):
                # In case the user attempts an action not allowed in their current plan,
                # we merely log that message at INFO level (so the user is aware,
                # but not spammed with ERROR messages that they cannot change):
                LOGGER.info(result)

            if isinstance(result, SimplipyError):
                raise UpdateFailed(f"SimpliSafe error while updating: {result}")


class SimpliSafeEntity(CoordinatorEntity):
    """Define a base SimpliSafe entity."""

    def __init__(self, simplisafe, system, name, *, serial=None):
        """Initialize."""
        super().__init__(simplisafe.coordinator)
        self._name = name
        self._online = True
        self._simplisafe = simplisafe
        self._system = system

        if serial:
            self._serial = serial
        else:
            self._serial = system.serial

        self._attrs = {ATTR_SYSTEM_ID: system.system_id}

        self._device_info = {
            "identifiers": {(DOMAIN, system.system_id)},
            "manufacturer": "SimpliSafe",
            "model": system.version,
            "name": name,
            "via_device": (DOMAIN, system.serial),
        }

    @property
    def available(self):
        """Return whether the entity is available."""
        # We can easily detect if the V3 system is offline, but no simple check exists
        # for the V2 system. Therefore, assuming the coordinator hasn't failed, we mark
        # the entity as available if:
        #   1. We can verify that the system is online (assuming True if we can't)
        #   2. We can verify that the entity is online
        return not (self._system.version == 3 and self._system.offline) and self._online

    @property
    def device_info(self):
        """Return device registry information for this entity."""
        return self._device_info

    @property
    def extra_state_attributes(self):
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
    def _handle_coordinator_update(self):
        """Update the entity with new REST API data."""
        self.async_update_from_rest_api()
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register callbacks."""
        await super().async_added_to_hass()
        self.async_update_from_rest_api()

    @callback
    def async_update_from_rest_api(self):
        """Update the entity with the provided REST API data."""
        raise NotImplementedError()


class SimpliSafeBaseSensor(SimpliSafeEntity):
    """Define a SimpliSafe base (binary) sensor."""

    def __init__(self, simplisafe, system, sensor):
        """Initialize."""
        super().__init__(simplisafe, system, sensor.name, serial=sensor.serial)
        self._device_info["identifiers"] = {(DOMAIN, sensor.serial)}
        self._device_info["model"] = sensor.type.name
        self._device_info["name"] = sensor.name
        self._sensor = sensor
        self._sensor_type_human_name = " ".join(
            [w.title() for w in self._sensor.type.name.split("_")]
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._system.address} {self._name} {self._sensor_type_human_name}"
