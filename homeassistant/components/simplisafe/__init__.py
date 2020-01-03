"""Support for SimpliSafe alarm systems."""
import asyncio
from datetime import timedelta
import logging

from simplipy import API
from simplipy.errors import InvalidCredentialsError, SimplipyError
from simplipy.system.v3 import LevelMap as V3Volume
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_CODE,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_USERNAME,
    STATE_HOME,
)
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
from homeassistant.helpers.service import verify_domain_control

from .config_flow import configured_instances
from .const import DATA_CLIENT, DEFAULT_SCAN_INTERVAL, DOMAIN, TOPIC_UPDATE

_LOGGER = logging.getLogger(__name__)

CONF_ACCOUNTS = "accounts"

DATA_LISTENER = "listener"

ATTR_ARMED_LIGHT_STATE = "armed_light_state"
ATTR_ARRIVAL_STATE = "arrival_state"
ATTR_PIN_LABEL = "label"
ATTR_PIN_LABEL_OR_VALUE = "label_or_pin"
ATTR_PIN_VALUE = "pin"
ATTR_SECONDS = "seconds"
ATTR_SYSTEM_ID = "system_id"
ATTR_TRANSITION = "transition"
ATTR_VOLUME = "volume"
ATTR_VOLUME_PROPERTY = "volume_property"

STATE_AWAY = "away"
STATE_ENTRY = "entry"
STATE_EXIT = "exit"

VOLUME_PROPERTY_ALARM = "alarm"
VOLUME_PROPERTY_CHIME = "chime"
VOLUME_PROPERTY_VOICE_PROMPT = "voice_prompt"

SERVICE_BASE_SCHEMA = vol.Schema({vol.Required(ATTR_SYSTEM_ID): cv.positive_int})

SERVICE_REMOVE_PIN_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {vol.Required(ATTR_PIN_LABEL_OR_VALUE): cv.string}
)

SERVICE_SET_DELAY_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {
        vol.Required(ATTR_ARRIVAL_STATE): vol.In((STATE_AWAY, STATE_HOME)),
        vol.Required(ATTR_TRANSITION): vol.In((STATE_ENTRY, STATE_EXIT)),
        vol.Required(ATTR_SECONDS): cv.positive_int,
    }
)

SERVICE_SET_LIGHT_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {vol.Required(ATTR_ARMED_LIGHT_STATE): cv.boolean}
)

SERVICE_SET_PIN_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {vol.Required(ATTR_PIN_LABEL): cv.string, vol.Required(ATTR_PIN_VALUE): cv.string}
)

SERVICE_SET_VOLUME_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {
        vol.Required(ATTR_VOLUME_PROPERTY): vol.In(
            (VOLUME_PROPERTY_ALARM, VOLUME_PROPERTY_CHIME, VOLUME_PROPERTY_VOICE_PROMPT)
        ),
        vol.Required(ATTR_VOLUME): cv.string,
    }
)

ACCOUNT_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_CODE): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
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
def _async_get_refresh_token(hass, config_entry):
    """Retrieve a refresh token from the config entry."""
    entry = hass.config_entries.async_get_entry(config_entry.entry_id)
    return entry.data[CONF_TOKEN]


@callback
def _async_save_refresh_token(hass, config_entry, token):
    """Save a refresh token to the config entry."""
    hass.config_entries.async_update_entry(
        config_entry, data={**config_entry.data, CONF_TOKEN: token}
    )


def async_guard_api_call(hass, config_entry, api):
    """Guard a call against the SimpliSafe API.

    At times, SimpliSafe can inexplicably invalidate the internal refresh token used by
    simplisafe-python (thus terminating the refresh logic within the library). In this
    case, we re-authenticate using the refresh token stored in the config entry (which
    is consistently shown to be good).

    Note that the API call is not automatically tried again.
    """

    def decorator(coro):
        """Decorate."""

        async def wrapper(*args, **kwargs):
            """Wrap an API call coroutine."""
            try:
                await coro(*args, **kwargs)
            except InvalidCredentialsError:
                _LOGGER.warning("SimpliSafe expired token; refreshing from storage")
                refresh_token = _async_get_refresh_token(hass, config_entry)
                await api.refresh_access_token(refresh_token)
            except SimplipyError as err:
                _LOGGER.error(
                    'SimpliSafe error while calling "%s": %s', coro.__name__, err
                )
                return
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.error(
                    'Unknown error while calling "%s": %s', coro.__name__, err
                )
                return

            # If simplisafe-python detects a new refresh token, save it to the config
            # entry:
            if api.refresh_token_dirty:
                _async_save_refresh_token(hass, config_entry, api.refresh_token)

        return wrapper

    return decorator


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
                    CONF_SCAN_INTERVAL: account[CONF_SCAN_INTERVAL],
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
        hass, refresh, timedelta(seconds=config_entry.data[CONF_SCAN_INTERVAL])
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
        await async_guard_api_call(hass, config_entry, api)(system.remove_pin)(
            call.data[ATTR_PIN_LABEL_OR_VALUE]
        )

    @verify_system_exists
    @v3_only
    @_verify_domain_control
    async def set_alarm_duration(call):
        """Set the duration of a running alarm."""
        system = systems[call.data[ATTR_SYSTEM_ID]]
        await async_guard_api_call(hass, config_entry, api)(system.set_alarm_duration)(
            call.data[ATTR_SECONDS]
        )

    @verify_system_exists
    @v3_only
    @_verify_domain_control
    async def set_delay(call):
        """Set the delay duration for entry/exit, away/home (any combo)."""
        system = systems[call.data[ATTR_SYSTEM_ID]]
        coro = getattr(
            system,
            f"set_{call.data[ATTR_TRANSITION]}_delay_{call.data[ATTR_ARRIVAL_STATE]}",
        )

        await async_guard_api_call(hass, config_entry, api)(coro)(
            call.data[ATTR_SECONDS]
        )

    @verify_system_exists
    @v3_only
    @_verify_domain_control
    async def set_armed_light(call):
        """Turn the base station light on/off."""
        system = systems[call.data[ATTR_SYSTEM_ID]]
        await async_guard_api_call(hass, config_entry, api)(system.set_light)(
            call.data[ATTR_ARMED_LIGHT_STATE]
        )

    @verify_system_exists
    @_verify_domain_control
    async def set_pin(call):
        """Set a PIN."""
        system = systems[call.data[ATTR_SYSTEM_ID]]
        await async_guard_api_call(hass, config_entry, api)(system.set_pin)(
            call.data[ATTR_PIN_LABEL], call.data[ATTR_PIN_VALUE]
        )

    @verify_system_exists
    @v3_only
    @_verify_domain_control
    async def set_volume_property(call):
        """Set a volume parameter in an appropriate service call."""
        system = systems[call.data[ATTR_SYSTEM_ID]]
        try:
            volume = V3Volume[call.data[ATTR_VOLUME]]
        except KeyError:
            _LOGGER.error("Unknown volume string: %s", call.data[ATTR_VOLUME])
            return
        except SimplipyError as err:
            _LOGGER.error("Error during service call: %s", err)
            return
        else:
            coro = getattr(system, f"set_{call.data[ATTR_VOLUME_PROPERTY]}_volume")
            await async_guard_api_call(hass, config_entry, api)(coro)(volume)

    for service, method, schema in [
        ("remove_pin", remove_pin, SERVICE_REMOVE_PIN_SCHEMA),
        ("set_alarm_duration", set_alarm_duration, SERVICE_SET_DELAY_SCHEMA),
        ("set_delay", set_delay, SERVICE_SET_DELAY_SCHEMA),
        ("set_armed_light", set_armed_light, SERVICE_SET_LIGHT_SCHEMA),
        ("set_pin", set_pin, SERVICE_SET_PIN_SCHEMA),
        ("set_volume_property", set_volume_property, SERVICE_SET_VOLUME_SCHEMA),
    ]:
        hass.services.async_register(DOMAIN, service, method, schema=schema)

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
        self._config_entry = config_entry
        self._hass = hass
        self.api = api
        self.last_event_data = {}
        self.systems = systems

    async def _update_system(self, system):
        """Update a system."""
        await system.update()
        latest_event = await system.get_latest_event()
        self.last_event_data[system.system_id] = latest_event

    async def async_update(self):
        """Get updated data from SimpliSafe."""
        tasks = [
            async_guard_api_call(self._hass, self._config_entry, self.api)(
                self._update_system
            )(system)
            for system in self.systems.values()
        ]

        await asyncio.gather(*tasks)


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
