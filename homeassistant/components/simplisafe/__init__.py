"""Support for SimpliSafe alarm systems."""
import asyncio
import logging

from simplipy import API
from simplipy.errors import InvalidCredentialsError, SimplipyError
from simplipy.system.v3 import VOLUME_HIGH, VOLUME_LOW, VOLUME_MEDIUM, VOLUME_OFF
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_CODE, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import callback
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

from .config_flow import configured_instances
from .const import DATA_CLIENT, DEFAULT_SCAN_INTERVAL, DOMAIN, TOPIC_UPDATE

_LOGGER = logging.getLogger(__name__)

CONF_ACCOUNTS = "accounts"

DATA_LISTENER = "listener"

ATTR_ALARM_DURATION = "alarm_duration"
ATTR_ALARM_VOLUME = "alarm_volume"
ATTR_CHIME_VOLUME = "chime_volume"
ATTR_ENTRY_DELAY_AWAY = "entry_delay_away"
ATTR_ENTRY_DELAY_HOME = "entry_delay_home"
ATTR_EXIT_DELAY_AWAY = "exit_delay_away"
ATTR_EXIT_DELAY_HOME = "exit_delay_home"
ATTR_LIGHT = "light"
ATTR_PIN_LABEL = "label"
ATTR_PIN_LABEL_OR_VALUE = "label_or_pin"
ATTR_PIN_VALUE = "pin"
ATTR_SYSTEM_ID = "system_id"
ATTR_VOICE_PROMPT_VOLUME = "voice_prompt_volume"

VOLUMES = [VOLUME_OFF, VOLUME_LOW, VOLUME_MEDIUM, VOLUME_HIGH]

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
        if account[CONF_USERNAME] in configured_instances(hass):
            continue

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
    _verify_domain_control = verify_domain_control(hass, DOMAIN)

    websession = aiohttp_client.async_get_clientsession(hass)

    try:
        api = await API.login_via_token(config_entry.data[CONF_TOKEN], websession)
    except InvalidCredentialsError:
        _LOGGER.error("Invalid credentials provided")
        return False
    except SimplipyError as err:
        _LOGGER.error("Config entry failed: %s", err)
        raise ConfigEntryNotReady

    _async_save_refresh_token(hass, config_entry, api.refresh_token)

    systems = await api.get_systems()
    simplisafe = SimpliSafe(hass, api, systems, config_entry)
    await simplisafe.async_update()
    hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id] = simplisafe

    for component in ("alarm_control_panel", "lock"):
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    async def refresh(event_time):
        """Refresh data from the SimpliSafe account."""
        await simplisafe.async_update()
        _LOGGER.debug("Updated data for all SimpliSafe systems")
        async_dispatcher_send(hass, TOPIC_UPDATE)

    hass.data[DOMAIN][DATA_LISTENER][config_entry.entry_id] = async_track_time_interval(
        hass, refresh, DEFAULT_SCAN_INTERVAL
    )

    # Register the base station for each system:
    for system in systems.values():
        hass.async_create_task(
            async_register_base_station(hass, system, config_entry.entry_id)
        )

    @callback
    def verify_system_exists(coro):
        """Log an error if a service call uses an invalid system ID."""

        async def decorator(call):
            """Decorate."""
            system_id = int(call.data[ATTR_SYSTEM_ID])
            if system_id not in systems:
                _LOGGER.error("Unknown system ID in service call: %s", system_id)
                return
            await coro(call)

        return decorator

    @callback
    def v3_only(coro):
        """Log an error if the decorated coroutine is called with a v2 system."""

        async def decorator(call):
            """Decorate."""
            system = systems[int(call.data[ATTR_SYSTEM_ID])]
            if system.version != 3:
                _LOGGER.error("Service only available on V3 systems")
                return
            await coro(call)

        return decorator

    @verify_system_exists
    @_verify_domain_control
    async def remove_pin(call):
        """Remove a PIN."""
        system = systems[call.data[ATTR_SYSTEM_ID]]
        try:
            await system.remove_pin(call.data[ATTR_PIN_LABEL_OR_VALUE])
        except SimplipyError as err:
            _LOGGER.error("Error during service call: %s", err)
            return

    @verify_system_exists
    @_verify_domain_control
    async def set_pin(call):
        """Set a PIN."""
        system = systems[call.data[ATTR_SYSTEM_ID]]
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
        system = systems[call.data[ATTR_SYSTEM_ID]]
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
        ("remove_pin", remove_pin, SERVICE_REMOVE_PIN_SCHEMA),
        ("set_pin", set_pin, SERVICE_SET_PIN_SCHEMA),
        (
            "set_system_properties",
            set_system_properties,
            SERVICE_SET_SYSTEM_PROPERTIES_SCHEMA,
        ),
    ]:
        async_register_admin_service(hass, DOMAIN, service, method, schema=schema)

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


class SimpliSafe:
    """Define a SimpliSafe API object."""

    def __init__(self, hass, api, systems, config_entry):
        """Initialize."""
        self._api = api
        self._config_entry = config_entry
        self._emergency_refresh_token_used = False
        self._hass = hass
        self.last_event_data = {}
        self.systems = systems

    async def _update_system(self, system):
        """Update a system."""
        try:
            await system.update()
        except InvalidCredentialsError:
            # SimpliSafe's cloud is a little shaky. At times, a 500 or 502 will
            # seemingly harm simplisafe-python's existing access token _and_ refresh
            # token, thus preventing the integration from recovering. However, the
            # refresh token stored in the config entry escapes unscathed (again,
            # apparently); so, if we detect that we're in such a situation, try a last-
            # ditch effort by re-authenticating with the stored token:
            if self._emergency_refresh_token_used:
                # If we've already tried this, log the error, suggest a HASS restart,
                # and stop the time tracker:
                _LOGGER.error(
                    "SimpliSafe authentication disconnected. Please restart HASS."
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
        except SimplipyError as err:
            _LOGGER.error(
                'SimpliSafe error while updating "%s": %s', system.address, err
            )
            return
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error('Unknown error while updating "%s": %s', system.address, err)
            return

        self.last_event_data[system.system_id] = await system.get_latest_event()

        # If we've reached this point using an emergency refresh token, we're in the
        # clear and we can discard it:
        if self._emergency_refresh_token_used:
            self._emergency_refresh_token_used = False

    async def async_update(self):
        """Get updated data from SimpliSafe."""
        tasks = [self._update_system(system) for system in self.systems.values()]

        await asyncio.gather(*tasks)

        if self._api.refresh_token_dirty:
            _async_save_refresh_token(
                self._hass, self._config_entry, self._api.refresh_token
            )


class SimpliSafeEntity(Entity):
    """Define a base SimpliSafe entity."""

    def __init__(self, system, name, *, serial=None):
        """Initialize."""
        self._async_unsub_dispatcher_connect = None
        self._attrs = {ATTR_SYSTEM_ID: system.system_id}
        self._name = name
        self._online = True
        self._system = system

        if serial:
            self._serial = serial
        else:
            self._serial = system.serial

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

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self._async_unsub_dispatcher_connect = async_dispatcher_connect(
            self.hass, TOPIC_UPDATE, update
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect dispatcher listener when removed."""
        if self._async_unsub_dispatcher_connect:
            self._async_unsub_dispatcher_connect()
