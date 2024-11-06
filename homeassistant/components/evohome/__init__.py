"""Support for (EMEA/EU-based) Honeywell TCC systems.

Such systems provide heating/cooling and DHW and include Evohome, Round Thermostat, and
others.
"""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, Final

import evohomeasync as ev1
from evohomeasync.schema import SZ_SESSION_ID
import evohomeasync2 as evo
from evohomeasync2.schema.const import (
    SZ_AUTO_WITH_RESET,
    SZ_CAN_BE_TEMPORARY,
    SZ_SYSTEM_MODE,
    SZ_TIMING_MODE,
)
import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.service import verify_domain_control
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
import homeassistant.util.dt as dt_util

from .const import (
    ACCESS_TOKEN,
    ACCESS_TOKEN_EXPIRES,
    ATTR_DURATION_DAYS,
    ATTR_DURATION_HOURS,
    ATTR_DURATION_UNTIL,
    ATTR_SYSTEM_MODE,
    ATTR_ZONE_TEMP,
    CONF_LOCATION_IDX,
    DOMAIN,
    REFRESH_TOKEN,
    SCAN_INTERVAL_DEFAULT,
    SCAN_INTERVAL_MINIMUM,
    STORAGE_KEY,
    STORAGE_VER,
    USER_DATA,
    EvoService,
)
from .coordinator import EvoBroker
from .helpers import dt_aware_to_naive, dt_local_to_aware, handle_evo_exception

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA: Final = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_LOCATION_IDX, default=0): cv.positive_int,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=SCAN_INTERVAL_DEFAULT
                ): vol.All(cv.time_period, vol.Range(min=SCAN_INTERVAL_MINIMUM)),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

# system mode schemas are built dynamically when the services are registered
# because supported modes can vary for edge-case systems

RESET_ZONE_OVERRIDE_SCHEMA: Final = vol.Schema(
    {vol.Required(ATTR_ENTITY_ID): cv.entity_id}
)
SET_ZONE_OVERRIDE_SCHEMA: Final = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_ZONE_TEMP): vol.All(
            vol.Coerce(float), vol.Range(min=4.0, max=35.0)
        ),
        vol.Optional(ATTR_DURATION_UNTIL): vol.All(
            cv.time_period, vol.Range(min=timedelta(days=0), max=timedelta(days=1))
        ),
    }
)


class EvoSession:
    """Class for evohome client instantiation & authentication."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the evohome broker and its data structure."""

        self.hass = hass

        self._session = async_get_clientsession(hass)
        self._store = Store[dict[str, Any]](hass, STORAGE_VER, STORAGE_KEY)

        # the main client, which uses the newer API
        self.client_v2: evo.EvohomeClient | None = None
        self._tokens: dict[str, Any] = {}

        # the older client can be used to obtain high-precision temps (only)
        self.client_v1: ev1.EvohomeClient | None = None
        self.session_id: str | None = None

    async def authenticate(self, username: str, password: str) -> None:
        """Check the user credentials against the web API.

        Will raise evo.AuthenticationFailed if the credentials are invalid.
        """

        if (
            self.client_v2 is None
            or username != self.client_v2.username
            or password != self.client_v2.password
        ):
            await self._load_auth_tokens(username)

            client_v2 = evo.EvohomeClient(
                username,
                password,
                **self._tokens,
                session=self._session,
            )

        else:  # force a re-authentication
            client_v2 = self.client_v2
            client_v2._user_account = None  # noqa: SLF001

        await client_v2.login()
        self.client_v2 = client_v2  # only set attr if authentication succeeded

        await self.save_auth_tokens()

        self.client_v1 = ev1.EvohomeClient(
            username,
            password,
            session_id=self.session_id,
            session=self._session,
        )

    async def _load_auth_tokens(self, username: str) -> None:
        """Load access tokens and session_id from the store and validate them.

        Sets self._tokens and self._session_id to the latest values.
        """

        app_storage: dict[str, Any] = dict(await self._store.async_load() or {})

        if app_storage.pop(CONF_USERNAME, None) != username:
            # any tokens won't be valid, and store might be corrupt
            await self._store.async_save({})

            self.session_id = None
            self._tokens = {}

            return

        # evohomeasync2 requires naive/local datetimes as strings
        if app_storage.get(ACCESS_TOKEN_EXPIRES) is not None and (
            expires := dt_util.parse_datetime(app_storage[ACCESS_TOKEN_EXPIRES])
        ):
            app_storage[ACCESS_TOKEN_EXPIRES] = dt_aware_to_naive(expires)

        user_data: dict[str, str] = app_storage.pop(USER_DATA, {}) or {}

        self.session_id = user_data.get(SZ_SESSION_ID)
        self._tokens = app_storage

    async def save_auth_tokens(self) -> None:
        """Save access tokens and session_id to the store.

        Sets self._tokens and self._session_id to the latest values.
        """

        if self.client_v2 is None:
            await self._store.async_save({})
            return

        # evohomeasync2 uses naive/local datetimes
        access_token_expires = dt_local_to_aware(
            self.client_v2.access_token_expires  # type: ignore[arg-type]
        )

        self._tokens = {
            CONF_USERNAME: self.client_v2.username,
            REFRESH_TOKEN: self.client_v2.refresh_token,
            ACCESS_TOKEN: self.client_v2.access_token,
            ACCESS_TOKEN_EXPIRES: access_token_expires.isoformat(),
        }

        self.session_id = self.client_v1.broker.session_id if self.client_v1 else None

        app_storage = self._tokens
        if self.client_v1:
            app_storage[USER_DATA] = {SZ_SESSION_ID: self.session_id}

        await self._store.async_save(app_storage)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Evohome integration."""

    sess = EvoSession(hass)

    try:
        await sess.authenticate(
            config[DOMAIN][CONF_USERNAME],
            config[DOMAIN][CONF_PASSWORD],
        )

    except (evo.AuthenticationFailed, evo.RequestFailed) as err:
        handle_evo_exception(err)
        return False

    finally:
        config[DOMAIN][CONF_PASSWORD] = "REDACTED"

    broker = EvoBroker(sess)

    if not broker.validate_location(
        config[DOMAIN][CONF_LOCATION_IDX],
    ):
        return False

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_coordinator",
        update_interval=config[DOMAIN][CONF_SCAN_INTERVAL],
        update_method=broker.async_update,
    )
    await coordinator.async_register_shutdown()

    hass.data[DOMAIN] = {"broker": broker, "coordinator": coordinator}

    # without a listener, _schedule_refresh() won't be invoked by _async_refresh()
    coordinator.async_add_listener(lambda: None)
    await coordinator.async_refresh()  # get initial state

    hass.async_create_task(
        async_load_platform(hass, Platform.CLIMATE, DOMAIN, {}, config)
    )
    if broker.tcs.hotwater:
        hass.async_create_task(
            async_load_platform(hass, Platform.WATER_HEATER, DOMAIN, {}, config)
        )

    setup_service_functions(hass, broker)

    return True


@callback
def setup_service_functions(hass: HomeAssistant, broker: EvoBroker) -> None:
    """Set up the service handlers for the system/zone operating modes.

    Not all Honeywell TCC-compatible systems support all operating modes. In addition,
    each mode will require any of four distinct service schemas. This has to be
    enumerated before registering the appropriate handlers.

    It appears that all TCC-compatible systems support the same three zones modes.
    """

    @verify_domain_control(hass, DOMAIN)
    async def force_refresh(call: ServiceCall) -> None:
        """Obtain the latest state data via the vendor's RESTful API."""
        await broker.async_update()

    @verify_domain_control(hass, DOMAIN)
    async def set_system_mode(call: ServiceCall) -> None:
        """Set the system mode."""
        payload = {
            "unique_id": broker.tcs.systemId,
            "service": call.service,
            "data": call.data,
        }
        async_dispatcher_send(hass, DOMAIN, payload)

    @verify_domain_control(hass, DOMAIN)
    async def set_zone_override(call: ServiceCall) -> None:
        """Set the zone override (setpoint)."""
        entity_id = call.data[ATTR_ENTITY_ID]

        registry = er.async_get(hass)
        registry_entry = registry.async_get(entity_id)

        if registry_entry is None or registry_entry.platform != DOMAIN:
            raise ValueError(f"'{entity_id}' is not a known {DOMAIN} entity")

        if registry_entry.domain != "climate":
            raise ValueError(f"'{entity_id}' is not an {DOMAIN} controller/zone")

        payload = {
            "unique_id": registry_entry.unique_id,
            "service": call.service,
            "data": call.data,
        }

        async_dispatcher_send(hass, DOMAIN, payload)

    hass.services.async_register(DOMAIN, EvoService.REFRESH_SYSTEM, force_refresh)

    # Enumerate which operating modes are supported by this system
    modes = broker.tcs.allowedSystemModes

    # Not all systems support "AutoWithReset": register this handler only if required
    if [m[SZ_SYSTEM_MODE] for m in modes if m[SZ_SYSTEM_MODE] == SZ_AUTO_WITH_RESET]:
        hass.services.async_register(DOMAIN, EvoService.RESET_SYSTEM, set_system_mode)

    system_mode_schemas = []
    modes = [m for m in modes if m[SZ_SYSTEM_MODE] != SZ_AUTO_WITH_RESET]

    # Permanent-only modes will use this schema
    perm_modes = [m[SZ_SYSTEM_MODE] for m in modes if not m[SZ_CAN_BE_TEMPORARY]]
    if perm_modes:  # any of: "Auto", "HeatingOff": permanent only
        schema = vol.Schema({vol.Required(ATTR_SYSTEM_MODE): vol.In(perm_modes)})
        system_mode_schemas.append(schema)

    modes = [m for m in modes if m[SZ_CAN_BE_TEMPORARY]]

    # These modes are set for a number of hours (or indefinitely): use this schema
    temp_modes = [m[SZ_SYSTEM_MODE] for m in modes if m[SZ_TIMING_MODE] == "Duration"]
    if temp_modes:  # any of: "AutoWithEco", permanent or for 0-24 hours
        schema = vol.Schema(
            {
                vol.Required(ATTR_SYSTEM_MODE): vol.In(temp_modes),
                vol.Optional(ATTR_DURATION_HOURS): vol.All(
                    cv.time_period,
                    vol.Range(min=timedelta(hours=0), max=timedelta(hours=24)),
                ),
            }
        )
        system_mode_schemas.append(schema)

    # These modes are set for a number of days (or indefinitely): use this schema
    temp_modes = [m[SZ_SYSTEM_MODE] for m in modes if m[SZ_TIMING_MODE] == "Period"]
    if temp_modes:  # any of: "Away", "Custom", "DayOff", permanent or for 1-99 days
        schema = vol.Schema(
            {
                vol.Required(ATTR_SYSTEM_MODE): vol.In(temp_modes),
                vol.Optional(ATTR_DURATION_DAYS): vol.All(
                    cv.time_period,
                    vol.Range(min=timedelta(days=1), max=timedelta(days=99)),
                ),
            }
        )
        system_mode_schemas.append(schema)

    if system_mode_schemas:
        hass.services.async_register(
            DOMAIN,
            EvoService.SET_SYSTEM_MODE,
            set_system_mode,
            schema=vol.Schema(vol.Any(*system_mode_schemas)),
        )

    # The zone modes are consistent across all systems and use the same schema
    hass.services.async_register(
        DOMAIN,
        EvoService.RESET_ZONE_OVERRIDE,
        set_zone_override,
        schema=RESET_ZONE_OVERRIDE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        EvoService.SET_ZONE_OVERRIDE,
        set_zone_override,
        schema=SET_ZONE_OVERRIDE_SCHEMA,
    )
