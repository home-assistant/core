"""Support for (EMEA/EU-based) Honeywell TCC climate systems.

Such systems include evohome, Round Thermostat, and others.
"""

from __future__ import annotations

from collections.abc import Awaitable
from datetime import datetime, timedelta
from http import HTTPStatus
import logging
import re
from typing import Any

import evohomeasync as ev1
from evohomeasync.schema import SZ_ID, SZ_SESSION_ID, SZ_TEMP
import evohomeasync2 as evo
from evohomeasync2.schema.const import (
    SZ_ALLOWED_SYSTEM_MODES,
    SZ_AUTO_WITH_RESET,
    SZ_CAN_BE_TEMPORARY,
    SZ_GATEWAY_ID,
    SZ_GATEWAY_INFO,
    SZ_HEAT_SETPOINT,
    SZ_LOCATION_ID,
    SZ_LOCATION_INFO,
    SZ_SETPOINT_STATUS,
    SZ_STATE_STATUS,
    SZ_SYSTEM_MODE,
    SZ_SYSTEM_MODE_STATUS,
    SZ_TIME_UNTIL,
    SZ_TIME_ZONE,
    SZ_TIMING_MODE,
    SZ_UNTIL,
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
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.service import verify_domain_control
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as dt_util

from .const import DOMAIN, GWS, STORAGE_KEY, STORAGE_VER, TCS, UTC_OFFSET

_LOGGER = logging.getLogger(__name__)

ACCESS_TOKEN = "access_token"
ACCESS_TOKEN_EXPIRES = "access_token_expires"
REFRESH_TOKEN = "refresh_token"
USER_DATA = "user_data"

CONF_LOCATION_IDX = "location_idx"

SCAN_INTERVAL_DEFAULT = timedelta(seconds=300)
SCAN_INTERVAL_MINIMUM = timedelta(seconds=60)

CONFIG_SCHEMA = vol.Schema(
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

ATTR_SYSTEM_MODE = "mode"
ATTR_DURATION_DAYS = "period"
ATTR_DURATION_HOURS = "duration"

ATTR_ZONE_TEMP = "setpoint"
ATTR_DURATION_UNTIL = "duration"

SVC_REFRESH_SYSTEM = "refresh_system"
SVC_SET_SYSTEM_MODE = "set_system_mode"
SVC_RESET_SYSTEM = "reset_system"
SVC_SET_ZONE_OVERRIDE = "set_zone_override"
SVC_RESET_ZONE_OVERRIDE = "clear_zone_override"


RESET_ZONE_OVERRIDE_SCHEMA = vol.Schema({vol.Required(ATTR_ENTITY_ID): cv.entity_id})
SET_ZONE_OVERRIDE_SCHEMA = vol.Schema(
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
# system mode schemas are built dynamically, below


def _dt_local_to_aware(dt_naive: datetime) -> datetime:
    dt_aware = dt_util.now() + (dt_naive - datetime.now())
    if dt_aware.microsecond >= 500000:
        dt_aware += timedelta(seconds=1)
    return dt_aware.replace(microsecond=0)


def _dt_aware_to_naive(dt_aware: datetime) -> datetime:
    dt_naive = datetime.now() + (dt_aware - dt_util.now())
    if dt_naive.microsecond >= 500000:
        dt_naive += timedelta(seconds=1)
    return dt_naive.replace(microsecond=0)


def convert_until(status_dict: dict, until_key: str) -> None:
    """Reformat a dt str from "%Y-%m-%dT%H:%M:%SZ" as local/aware/isoformat."""
    if until_key in status_dict and (  # only present for certain modes
        dt_utc_naive := dt_util.parse_datetime(status_dict[until_key])
    ):
        status_dict[until_key] = dt_util.as_local(dt_utc_naive).isoformat()


def convert_dict(dictionary: dict[str, Any]) -> dict[str, Any]:
    """Recursively convert a dict's keys to snake_case."""

    def convert_key(key: str) -> str:
        """Convert a string to snake_case."""
        string = re.sub(r"[\-\.\s]", "_", str(key))
        return (
            (string[0]).lower()
            + re.sub(
                r"[A-Z]",
                lambda matched: f"_{matched.group(0).lower()}",  # type:ignore[str-bytes-safe]
                string[1:],
            )
        )

    return {
        (convert_key(k) if isinstance(k, str) else k): (
            convert_dict(v) if isinstance(v, dict) else v
        )
        for k, v in dictionary.items()
    }


def _handle_exception(err: evo.RequestFailed) -> None:
    """Return False if the exception can't be ignored."""

    try:
        raise err

    except evo.AuthenticationFailed:
        _LOGGER.error(
            (
                "Failed to authenticate with the vendor's server. Check your username"
                " and password. NB: Some special password characters that work"
                " correctly via the website will not work via the web API. Message"
                " is: %s"
            ),
            err,
        )

    except evo.RequestFailed:
        if err.status is None:
            _LOGGER.warning(
                (
                    "Unable to connect with the vendor's server. "
                    "Check your network and the vendor's service status page. "
                    "Message is: %s"
                ),
                err,
            )

        elif err.status == HTTPStatus.SERVICE_UNAVAILABLE:
            _LOGGER.warning(
                "The vendor says their server is currently unavailable. "
                "Check the vendor's service status page"
            )

        elif err.status == HTTPStatus.TOO_MANY_REQUESTS:
            _LOGGER.warning(
                (
                    "The vendor's API rate limit has been exceeded. "
                    "If this message persists, consider increasing the %s"
                ),
                CONF_SCAN_INTERVAL,
            )

        else:
            raise  # we don't expect/handle any other Exceptions


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Create a (EMEA/EU-based) Honeywell TCC system."""

    async def load_auth_tokens(store: Store) -> tuple[dict, dict | None]:
        app_storage = await store.async_load()
        tokens = dict(app_storage or {})

        if tokens.pop(CONF_USERNAME, None) != config[DOMAIN][CONF_USERNAME]:
            # any tokens won't be valid, and store might be corrupt
            await store.async_save({})
            return ({}, {})

        # evohomeasync2 requires naive/local datetimes as strings
        if tokens.get(ACCESS_TOKEN_EXPIRES) is not None and (
            expires := dt_util.parse_datetime(tokens[ACCESS_TOKEN_EXPIRES])
        ):
            tokens[ACCESS_TOKEN_EXPIRES] = _dt_aware_to_naive(expires)

        user_data = tokens.pop(USER_DATA, {})
        return (tokens, user_data)

    store = Store[dict[str, Any]](hass, STORAGE_VER, STORAGE_KEY)
    tokens, user_data = await load_auth_tokens(store)

    client_v2 = evo.EvohomeClient(
        config[DOMAIN][CONF_USERNAME],
        config[DOMAIN][CONF_PASSWORD],
        **tokens,
        session=async_get_clientsession(hass),
    )

    try:
        await client_v2.login()
    except evo.AuthenticationFailed as err:
        _handle_exception(err)
        return False
    finally:
        config[DOMAIN][CONF_PASSWORD] = "REDACTED"

    loc_idx = config[DOMAIN][CONF_LOCATION_IDX]
    try:
        loc_config = client_v2.installation_info[loc_idx]
    except IndexError:
        _LOGGER.error(
            (
                "Config error: '%s' = %s, but the valid range is 0-%s. "
                "Unable to continue. Fix any configuration errors and restart HA"
            ),
            CONF_LOCATION_IDX,
            loc_idx,
            len(client_v2.installation_info) - 1,
        )
        return False

    if _LOGGER.isEnabledFor(logging.DEBUG):
        loc_info = {
            SZ_LOCATION_ID: loc_config[SZ_LOCATION_INFO][SZ_LOCATION_ID],
            SZ_TIME_ZONE: loc_config[SZ_LOCATION_INFO][SZ_TIME_ZONE],
        }
        gwy_info = {
            SZ_GATEWAY_ID: loc_config[GWS][0][SZ_GATEWAY_INFO][SZ_GATEWAY_ID],
            TCS: loc_config[GWS][0][TCS],
        }
        _config = {
            SZ_LOCATION_INFO: loc_info,
            GWS: [{SZ_GATEWAY_INFO: gwy_info, TCS: loc_config[GWS][0][TCS]}],
        }
        _LOGGER.debug("Config = %s", _config)

    client_v1 = ev1.EvohomeClient(
        client_v2.username,
        client_v2.password,
        session_id=user_data.get(SZ_SESSION_ID) if user_data else None,  # STORAGE_VER 1
        session=async_get_clientsession(hass),
    )

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN]["broker"] = broker = EvoBroker(
        hass, client_v2, client_v1, store, config[DOMAIN]
    )

    await broker.save_auth_tokens()
    await broker.async_update()  # get initial state

    hass.async_create_task(
        async_load_platform(hass, Platform.CLIMATE, DOMAIN, {}, config)
    )
    if broker.tcs.hotwater:
        hass.async_create_task(
            async_load_platform(hass, Platform.WATER_HEATER, DOMAIN, {}, config)
        )

    async_track_time_interval(
        hass, broker.async_update, config[DOMAIN][CONF_SCAN_INTERVAL]
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

    hass.services.async_register(DOMAIN, SVC_REFRESH_SYSTEM, force_refresh)

    # Enumerate which operating modes are supported by this system
    modes = broker.config[SZ_ALLOWED_SYSTEM_MODES]

    # Not all systems support "AutoWithReset": register this handler only if required
    if [m[SZ_SYSTEM_MODE] for m in modes if m[SZ_SYSTEM_MODE] == SZ_AUTO_WITH_RESET]:
        hass.services.async_register(DOMAIN, SVC_RESET_SYSTEM, set_system_mode)

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
            SVC_SET_SYSTEM_MODE,
            set_system_mode,
            schema=vol.Schema(vol.Any(*system_mode_schemas)),
        )

    # The zone modes are consistent across all systems and use the same schema
    hass.services.async_register(
        DOMAIN,
        SVC_RESET_ZONE_OVERRIDE,
        set_zone_override,
        schema=RESET_ZONE_OVERRIDE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SVC_SET_ZONE_OVERRIDE,
        set_zone_override,
        schema=SET_ZONE_OVERRIDE_SCHEMA,
    )


class EvoBroker:
    """Container for evohome client and data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: evo.EvohomeClient,
        client_v1: ev1.EvohomeClient | None,
        store: Store[dict[str, Any]],
        params: ConfigType,
    ) -> None:
        """Initialize the evohome client and its data structure."""
        self.hass = hass
        self.client = client
        self.client_v1 = client_v1
        self._store = store
        self.params = params

        loc_idx = params[CONF_LOCATION_IDX]
        self._location: evo.Location = client.locations[loc_idx]

        self.config = client.installation_info[loc_idx][GWS][0][TCS][0]
        self.tcs: evo.ControlSystem = self._location._gateways[0]._control_systems[0]
        self.tcs_utc_offset = timedelta(minutes=self._location.timeZone[UTC_OFFSET])
        self.temps: dict[str, float | None] = {}

    async def save_auth_tokens(self) -> None:
        """Save access tokens and session IDs to the store for later use."""
        # evohomeasync2 uses naive/local datetimes
        access_token_expires = _dt_local_to_aware(
            self.client.access_token_expires  # type: ignore[arg-type]
        )

        app_storage: dict[str, Any] = {
            CONF_USERNAME: self.client.username,
            REFRESH_TOKEN: self.client.refresh_token,
            ACCESS_TOKEN: self.client.access_token,
            ACCESS_TOKEN_EXPIRES: access_token_expires.isoformat(),
        }

        if self.client_v1:
            app_storage[USER_DATA] = {
                SZ_SESSION_ID: self.client_v1.broker.session_id,
            }  # this is the schema for STORAGE_VER == 1
        else:
            app_storage[USER_DATA] = {}

        await self._store.async_save(app_storage)

    async def call_client_api(
        self,
        client_api: Awaitable[dict[str, Any] | None],
        update_state: bool = True,
    ) -> dict[str, Any] | None:
        """Call a client API and update the broker state if required."""

        try:
            result = await client_api
        except evo.RequestFailed as err:
            _handle_exception(err)
            return None

        if update_state:  # wait a moment for system to quiesce before updating state
            async_call_later(self.hass, 1, self._update_v2_api_state)

        return result

    async def _update_v1_api_temps(self) -> None:
        """Get the latest high-precision temperatures of the default Location."""

        assert self.client_v1 is not None  # mypy check

        def get_session_id(client_v1: ev1.EvohomeClient) -> str | None:
            user_data = client_v1.user_data if client_v1 else None
            return user_data.get(SZ_SESSION_ID) if user_data else None  # type: ignore[return-value]

        session_id = get_session_id(self.client_v1)

        try:
            temps = await self.client_v1.get_temperatures()

        except ev1.InvalidSchema as err:
            _LOGGER.warning(
                (
                    "Unable to obtain high-precision temperatures. "
                    "It appears the JSON schema is not as expected, "
                    "so the high-precision feature will be disabled until next restart."
                    "Message is: %s"
                ),
                err,
            )
            self.client_v1 = None

        except ev1.RequestFailed as err:
            _LOGGER.warning(
                (
                    "Unable to obtain the latest high-precision temperatures. "
                    "Check your network and the vendor's service status page. "
                    "Proceeding without high-precision temperatures for now. "
                    "Message is: %s"
                ),
                err,
            )
            self.temps = {}  # high-precision temps now considered stale

        except Exception:
            self.temps = {}  # high-precision temps now considered stale
            raise

        else:
            if str(self.client_v1.location_id) != self._location.locationId:
                _LOGGER.warning(
                    "The v2 API's configured location doesn't match "
                    "the v1 API's default location (there is more than one location), "
                    "so the high-precision feature will be disabled until next restart"
                )
                self.client_v1 = None
            else:
                self.temps = {str(i[SZ_ID]): i[SZ_TEMP] for i in temps}

        finally:
            if self.client_v1 and session_id != self.client_v1.broker.session_id:
                await self.save_auth_tokens()

        _LOGGER.debug("Temperatures = %s", self.temps)

    async def _update_v2_api_state(self, *args: Any) -> None:
        """Get the latest modes, temperatures, setpoints of a Location."""

        access_token = self.client.access_token  # maybe receive a new token?

        try:
            status = await self._location.refresh_status()
        except evo.RequestFailed as err:
            _handle_exception(err)
        else:
            async_dispatcher_send(self.hass, DOMAIN)
            _LOGGER.debug("Status = %s", status)
        finally:
            if access_token != self.client.access_token:
                await self.save_auth_tokens()

    async def async_update(self, *args: Any) -> None:
        """Get the latest state data of an entire Honeywell TCC Location.

        This includes state data for a Controller and all its child devices, such as the
        operating mode of the Controller and the current temp of its children (e.g.
        Zones, DHW controller).
        """
        await self._update_v2_api_state()

        if self.client_v1:
            await self._update_v1_api_temps()


class EvoDevice(Entity):
    """Base for any evohome device.

    This includes the Controller, (up to 12) Heating Zones and (optionally) a
    DHW controller.
    """

    _attr_should_poll = False

    def __init__(
        self,
        evo_broker: EvoBroker,
        evo_device: evo.ControlSystem | evo.HotWater | evo.Zone,
    ) -> None:
        """Initialize the evohome entity."""
        self._evo_device = evo_device
        self._evo_broker = evo_broker
        self._evo_tcs = evo_broker.tcs

        self._device_state_attrs: dict[str, Any] = {}

    async def async_refresh(self, payload: dict | None = None) -> None:
        """Process any signals."""
        if payload is None:
            self.async_schedule_update_ha_state(force_refresh=True)
            return
        if payload["unique_id"] != self._attr_unique_id:
            return
        if payload["service"] in (SVC_SET_ZONE_OVERRIDE, SVC_RESET_ZONE_OVERRIDE):
            await self.async_zone_svc_request(payload["service"], payload["data"])
            return
        await self.async_tcs_svc_request(payload["service"], payload["data"])

    async def async_tcs_svc_request(self, service: str, data: dict[str, Any]) -> None:
        """Process a service request (system mode) for a controller."""
        raise NotImplementedError

    async def async_zone_svc_request(self, service: str, data: dict[str, Any]) -> None:
        """Process a service request (setpoint override) for a zone."""
        raise NotImplementedError

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the evohome-specific state attributes."""
        status = self._device_state_attrs
        if SZ_SYSTEM_MODE_STATUS in status:
            convert_until(status[SZ_SYSTEM_MODE_STATUS], SZ_TIME_UNTIL)
        if SZ_SETPOINT_STATUS in status:
            convert_until(status[SZ_SETPOINT_STATUS], SZ_UNTIL)
        if SZ_STATE_STATUS in status:
            convert_until(status[SZ_STATE_STATUS], SZ_UNTIL)

        return {"status": convert_dict(status)}

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        async_dispatcher_connect(self.hass, DOMAIN, self.async_refresh)


class EvoChild(EvoDevice):
    """Base for any evohome child.

    This includes (up to 12) Heating Zones and (optionally) a DHW controller.
    """

    _evo_id: str  # mypy hint

    def __init__(
        self, evo_broker: EvoBroker, evo_device: evo.HotWater | evo.Zone
    ) -> None:
        """Initialize a evohome Controller (hub)."""
        super().__init__(evo_broker, evo_device)

        self._schedule: dict[str, Any] = {}
        self._setpoints: dict[str, Any] = {}

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature of a Zone."""

        assert isinstance(self._evo_device, evo.HotWater | evo.Zone)  # mypy check

        if (temp := self._evo_broker.temps.get(self._evo_id)) is not None:
            # use high-precision temps if available
            return temp
        return self._evo_device.temperature

    @property
    def setpoints(self) -> dict[str, Any]:
        """Return the current/next setpoints from the schedule.

        Only Zones & DHW controllers (but not the TCS) can have schedules.
        """

        def _dt_evo_to_aware(dt_naive: datetime, utc_offset: timedelta) -> datetime:
            dt_aware = dt_naive.replace(tzinfo=dt_util.UTC) - utc_offset
            return dt_util.as_local(dt_aware)

        if not (schedule := self._schedule.get("DailySchedules")):
            return {}  # no scheduled setpoints when {'DailySchedules': []}

        day_time = dt_util.now()
        day_of_week = day_time.weekday()  # for evohome, 0 is Monday
        time_of_day = day_time.strftime("%H:%M:%S")

        try:
            # Iterate today's switchpoints until past the current time of day...
            day = schedule[day_of_week]
            sp_idx = -1  # last switchpoint of the day before
            for i, tmp in enumerate(day["Switchpoints"]):
                if time_of_day > tmp["TimeOfDay"]:
                    sp_idx = i  # current setpoint
                else:
                    break

            # Did the current SP start yesterday? Does the next start SP tomorrow?
            this_sp_day = -1 if sp_idx == -1 else 0
            next_sp_day = 1 if sp_idx + 1 == len(day["Switchpoints"]) else 0

            for key, offset, idx in (
                ("this", this_sp_day, sp_idx),
                ("next", next_sp_day, (sp_idx + 1) * (1 - next_sp_day)),
            ):
                sp_date = (day_time + timedelta(days=offset)).strftime("%Y-%m-%d")
                day = schedule[(day_of_week + offset) % 7]
                switchpoint = day["Switchpoints"][idx]

                switchpoint_time_of_day = dt_util.parse_datetime(
                    f"{sp_date}T{switchpoint['TimeOfDay']}"
                )
                assert switchpoint_time_of_day is not None  # mypy check
                dt_aware = _dt_evo_to_aware(
                    switchpoint_time_of_day, self._evo_broker.tcs_utc_offset
                )

                self._setpoints[f"{key}_sp_from"] = dt_aware.isoformat()
                try:
                    self._setpoints[f"{key}_sp_temp"] = switchpoint[SZ_HEAT_SETPOINT]
                except KeyError:
                    self._setpoints[f"{key}_sp_state"] = switchpoint["DhwState"]

        except IndexError:
            self._setpoints = {}
            _LOGGER.warning(
                "Failed to get setpoints, report as an issue if this error persists",
                exc_info=True,
            )

        return self._setpoints

    async def _update_schedule(self) -> None:
        """Get the latest schedule, if any."""

        assert isinstance(self._evo_device, evo.HotWater | evo.Zone)  # mypy check

        try:
            self._schedule = await self._evo_broker.call_client_api(  # type: ignore[assignment]
                self._evo_device.get_schedule(), update_state=False
            )
        except evo.InvalidSchedule as err:
            _LOGGER.warning(
                "%s: Unable to retrieve the schedule: %s",
                self._evo_device,
                err,
            )
            self._schedule = {}

        _LOGGER.debug("Schedule['%s'] = %s", self.name, self._schedule)

    async def async_update(self) -> None:
        """Get the latest state data."""
        next_sp_from = self._setpoints.get("next_sp_from", "2000-01-01T00:00:00+00:00")
        next_sp_from_dt = dt_util.parse_datetime(next_sp_from)
        if next_sp_from_dt is None or dt_util.now() >= next_sp_from_dt:
            await self._update_schedule()  # no schedule, or it's out-of-date

        self._device_state_attrs = {"setpoints": self.setpoints}
