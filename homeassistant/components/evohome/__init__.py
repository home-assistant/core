"""Support for (EMEA/EU-based) Honeywell TCC climate systems.

Such systems include evohome (multi-zone), and Round Thermostat (single zone).
"""
from datetime import datetime, timedelta
import logging
import re
from typing import Any, Dict, Optional, Tuple

import aiohttp.client_exceptions
import evohomeasync
import evohomeasync2
import voluptuous as vol

from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    HTTP_SERVICE_UNAVAILABLE,
    HTTP_TOO_MANY_REQUESTS,
    TEMP_CELSIUS,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
import homeassistant.util.dt as dt_util

from .const import DOMAIN, EVO_FOLLOW, GWS, STORAGE_KEY, STORAGE_VERSION, TCS

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


def _local_dt_to_aware(dt_naive: datetime) -> datetime:
    dt_aware = dt_util.now() + (dt_naive - datetime.now())
    if dt_aware.microsecond >= 500000:
        dt_aware += timedelta(seconds=1)
    return dt_aware.replace(microsecond=0)


def _dt_to_local_naive(dt_aware: datetime) -> datetime:
    dt_naive = datetime.now() + (dt_aware - dt_util.now())
    if dt_naive.microsecond >= 500000:
        dt_naive += timedelta(seconds=1)
    return dt_naive.replace(microsecond=0)


def convert_until(status_dict, until_key) -> str:
    """Convert datetime string from "%Y-%m-%dT%H:%M:%SZ" to local/aware/isoformat."""
    if until_key in status_dict:  # only present for certain modes
        dt_utc_naive = dt_util.parse_datetime(status_dict[until_key])
        status_dict[until_key] = dt_util.as_local(dt_utc_naive).isoformat()


def convert_dict(dictionary: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively convert a dict's keys to snake_case."""

    def convert_key(key: str) -> str:
        """Convert a string to snake_case."""
        string = re.sub(r"[\-\.\s]", "_", str(key))
        return (string[0]).lower() + re.sub(
            r"[A-Z]", lambda matched: "_" + matched.group(0).lower(), string[1:]
        )

    return {
        (convert_key(k) if isinstance(k, str) else k): (
            convert_dict(v) if isinstance(v, dict) else v
        )
        for k, v in dictionary.items()
    }


def _handle_exception(err) -> bool:
    """Return False if the exception can't be ignored."""
    try:
        raise err

    except evohomeasync2.AuthenticationError:
        _LOGGER.error(
            "Failed to authenticate with the vendor's server. "
            "Check your network and the vendor's service status page. "
            "Also check that your username and password are correct. "
            "Message is: %s",
            err,
        )
        return False

    except aiohttp.ClientConnectionError:
        # this appears to be common with Honeywell's servers
        _LOGGER.warning(
            "Unable to connect with the vendor's server. "
            "Check your network and the vendor's service status page. "
            "Message is: %s",
            err,
        )
        return False

    except aiohttp.ClientResponseError:
        if err.status == HTTP_SERVICE_UNAVAILABLE:
            _LOGGER.warning(
                "The vendor says their server is currently unavailable. "
                "Check the vendor's service status page."
            )
            return False

        if err.status == HTTP_TOO_MANY_REQUESTS:
            _LOGGER.warning(
                "The vendor's API rate limit has been exceeded. "
                "If this message persists, consider increasing the %s.",
                CONF_SCAN_INTERVAL,
            )
            return False

        raise  # we don't expect/handle any other Exceptions


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Create a (EMEA/EU-based) Honeywell evohome system."""

    async def load_auth_tokens(store) -> Tuple[Dict, Optional[Dict]]:
        app_storage = await store.async_load()
        tokens = dict(app_storage if app_storage else {})

        if tokens.pop(CONF_USERNAME, None) != config[DOMAIN][CONF_USERNAME]:
            # any tokens wont be valid, and store might be be corrupt
            await store.async_save({})
            return ({}, None)

        # evohomeasync2 requires naive/local datetimes as strings
        if tokens.get(ACCESS_TOKEN_EXPIRES) is not None:
            tokens[ACCESS_TOKEN_EXPIRES] = _dt_to_local_naive(
                dt_util.parse_datetime(tokens[ACCESS_TOKEN_EXPIRES])
            )

        user_data = tokens.pop(USER_DATA, None)
        return (tokens, user_data)

    store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
    tokens, user_data = await load_auth_tokens(store)

    client_v2 = evohomeasync2.EvohomeClient(
        config[DOMAIN][CONF_USERNAME],
        config[DOMAIN][CONF_PASSWORD],
        **tokens,
        session=async_get_clientsession(hass),
    )

    try:
        await client_v2.login()
    except (aiohttp.ClientError, evohomeasync2.AuthenticationError) as err:
        _handle_exception(err)
        return False
    finally:
        config[DOMAIN][CONF_PASSWORD] = "REDACTED"

    loc_idx = config[DOMAIN][CONF_LOCATION_IDX]
    try:
        loc_config = client_v2.installation_info[loc_idx][GWS][0][TCS][0]
    except IndexError:
        _LOGGER.error(
            "Config error: '%s' = %s, but the valid range is 0-%s. "
            "Unable to continue. Fix any configuration errors and restart HA.",
            CONF_LOCATION_IDX,
            loc_idx,
            len(client_v2.installation_info) - 1,
        )
        return False

    _LOGGER.debug("Config = %s", loc_config)

    client_v1 = evohomeasync.EvohomeClient(
        client_v2.username,
        client_v2.password,
        user_data=user_data,
        session=async_get_clientsession(hass),
    )

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN]["broker"] = broker = EvoBroker(
        hass, client_v2, client_v1, store, config[DOMAIN]
    )

    await broker.save_auth_tokens()
    await broker.update()  # get initial state

    hass.async_create_task(async_load_platform(hass, "climate", DOMAIN, {}, config))
    if broker.tcs.hotwater:
        hass.async_create_task(
            async_load_platform(hass, "water_heater", DOMAIN, {}, config)
        )

    hass.helpers.event.async_track_time_interval(
        broker.update, config[DOMAIN][CONF_SCAN_INTERVAL]
    )

    return True


class EvoBroker:
    """Container for evohome client and data."""

    def __init__(self, hass, client, client_v1, store, params) -> None:
        """Initialize the evohome client and its data structure."""
        self.hass = hass
        self.client = client
        self.client_v1 = client_v1
        self._store = store
        self.params = params

        loc_idx = params[CONF_LOCATION_IDX]
        self.config = client.installation_info[loc_idx][GWS][0][TCS][0]
        self.tcs = client.locations[loc_idx]._gateways[0]._control_systems[0]
        self.temps = None

    async def save_auth_tokens(self) -> None:
        """Save access tokens and session IDs to the store for later use."""
        # evohomeasync2 uses naive/local datetimes
        access_token_expires = _local_dt_to_aware(self.client.access_token_expires)

        app_storage = {CONF_USERNAME: self.client.username}
        app_storage[REFRESH_TOKEN] = self.client.refresh_token
        app_storage[ACCESS_TOKEN] = self.client.access_token
        app_storage[ACCESS_TOKEN_EXPIRES] = access_token_expires.isoformat()

        if self.client_v1 and self.client_v1.user_data:
            app_storage[USER_DATA] = {
                "userInfo": {"userID": self.client_v1.user_data["userInfo"]["userID"]},
                "sessionId": self.client_v1.user_data["sessionId"],
            }
        else:
            app_storage[USER_DATA] = None

        await self._store.async_save(app_storage)

    async def _update_v1(self, *args, **kwargs) -> None:
        """Get the latest high-precision temperatures of the default Location."""

        def get_session_id(client_v1) -> Optional[str]:
            user_data = client_v1.user_data if client_v1 else None
            return user_data.get("sessionId") if user_data else None

        session_id = get_session_id(self.client_v1)

        try:
            temps = list(await self.client_v1.temperatures(force_refresh=True))

        except aiohttp.ClientError as err:
            _LOGGER.warning(
                "Unable to obtain the latest high-precision temperatures. "
                "Check your network and the vendor's service status page. "
                "Proceeding with low-precision temperatures. "
                "Message is: %s",
                err,
            )
            self.temps = None  # these are now stale, will fall back to v2 temps

        else:
            if (
                str(self.client_v1.location_id)
                != self.client.locations[self.params[CONF_LOCATION_IDX]].locationId
            ):
                _LOGGER.warning(
                    "The v2 API's configured location doesn't match "
                    "the v1 API's default location (there is more than one location), "
                    "so the high-precision feature will be disabled"
                )
                self.client_v1 = self.temps = None
            else:
                self.temps = {str(i["id"]): i["temp"] for i in temps}

        _LOGGER.debug("Temperatures = %s", self.temps)

        if session_id != get_session_id(self.client_v1):
            await self.save_auth_tokens()

    async def _update_v2(self, *args, **kwargs) -> None:
        """Get the latest modes, temperatures, setpoints of a Location."""
        access_token = self.client.access_token

        loc_idx = self.params[CONF_LOCATION_IDX]
        try:
            status = await self.client.locations[loc_idx].status()
        except (aiohttp.ClientError, evohomeasync2.AuthenticationError) as err:
            _handle_exception(err)
        else:
            self.hass.helpers.dispatcher.async_dispatcher_send(DOMAIN)

            _LOGGER.debug("Status = %s", status[GWS][0][TCS][0])

        if access_token != self.client.access_token:
            await self.save_auth_tokens()

    async def update(self, *args, **kwargs) -> None:
        """Get the latest state data of an entire evohome Location.

        This includes state data for a Controller and all its child devices, such as the
        operating mode of the Controller and the current temp of its children (e.g.
        Zones, DHW controller).
        """
        await self._update_v2()

        if self.client_v1:
            await self._update_v1()

        # inform the evohome devices that state data has been updated
        self.hass.helpers.dispatcher.async_dispatcher_send(DOMAIN)


class EvoDevice(Entity):
    """Base for any evohome device.

    This includes the Controller, (up to 12) Heating Zones and (optionally) a
    DHW controller.
    """

    def __init__(self, evo_broker, evo_device) -> None:
        """Initialize the evohome entity."""
        self._evo_device = evo_device
        self._evo_broker = evo_broker
        self._evo_tcs = evo_broker.tcs

        self._unique_id = self._name = self._icon = self._precision = None
        self._supported_features = None
        self._device_state_attrs = {}

    @callback
    def _refresh(self) -> None:
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def should_poll(self) -> bool:
        """Evohome entities should not be polled."""
        return False

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name of the Evohome entity."""
        return self._name

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the Evohome-specific state attributes."""
        status = self._device_state_attrs
        if "systemModeStatus" in status:
            convert_until(status["systemModeStatus"], "timeUntil")
        if "setpointStatus" in status:
            convert_until(status["setpointStatus"], "until")
        if "stateStatus" in status:
            convert_until(status["stateStatus"], "until")

        return {"status": convert_dict(status)}

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend UI."""
        return self._icon

    @property
    def supported_features(self) -> int:
        """Get the flag of supported features of the device."""
        return self._supported_features

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self.hass.helpers.dispatcher.async_dispatcher_connect(DOMAIN, self._refresh)

    @property
    def precision(self) -> float:
        """Return the temperature precision to use in the frontend UI."""
        return self._precision

    @property
    def temperature_unit(self) -> str:
        """Return the temperature unit to use in the frontend UI."""
        return TEMP_CELSIUS

    async def _call_client_api(self, api_function, refresh=True) -> Any:
        try:
            result = await api_function
        except (aiohttp.ClientError, evohomeasync2.AuthenticationError) as err:
            if not _handle_exception(err):
                return

        if refresh is True:
            self.hass.helpers.event.async_call_later(1, self._evo_broker.update())

        return result


class EvoChild(EvoDevice):
    """Base for any evohome child.

    This includes (up to 12) Heating Zones and (optionally) a DHW controller.
    """

    def __init__(self, evo_broker, evo_device) -> None:
        """Initialize a evohome Controller (hub)."""
        super().__init__(evo_broker, evo_device)
        self._schedule = {}
        self._setpoints = {}

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature of a Zone."""
        if not self._evo_device.temperatureStatus["isAvailable"]:
            return None

        if self._evo_broker.temps:
            return self._evo_broker.temps[self._evo_device.zoneId]

        return self._evo_device.temperatureStatus["temperature"]

    @property
    def setpoints(self) -> Dict[str, Any]:
        """Return the current/next setpoints from the schedule.

        Only Zones & DHW controllers (but not the TCS) can have schedules.
        """
        if not self._schedule["DailySchedules"]:
            return {}  # no schedule {'DailySchedules': []}, so no scheduled setpoints

        day_time = dt_util.now()
        day_of_week = int(day_time.strftime("%w"))  # 0 is Sunday
        time_of_day = day_time.strftime("%H:%M:%S")

        try:
            # Iterate today's switchpoints until past the current time of day...
            day = self._schedule["DailySchedules"][day_of_week]
            sp_idx = -1  # last switchpoint of the day before
            for i, tmp in enumerate(day["Switchpoints"]):
                if time_of_day > tmp["TimeOfDay"]:
                    sp_idx = i  # current setpoint
                else:
                    break

            # Did the current SP start yesterday? Does the next start SP tomorrow?
            this_sp_day = -1 if sp_idx == -1 else 0
            next_sp_day = 1 if sp_idx + 1 == len(day["Switchpoints"]) else 0

            for key, offset, idx in [
                ("this", this_sp_day, sp_idx),
                ("next", next_sp_day, (sp_idx + 1) * (1 - next_sp_day)),
            ]:
                sp_date = (day_time + timedelta(days=offset)).strftime("%Y-%m-%d")
                day = self._schedule["DailySchedules"][(day_of_week + offset) % 7]
                switchpoint = day["Switchpoints"][idx]

                dt_local_aware = _local_dt_to_aware(
                    dt_util.parse_datetime(f"{sp_date}T{switchpoint['TimeOfDay']}")
                )

                self._setpoints[f"{key}_sp_from"] = dt_local_aware.isoformat()
                try:
                    self._setpoints[f"{key}_sp_temp"] = switchpoint["heatSetpoint"]
                except KeyError:
                    self._setpoints[f"{key}_sp_state"] = switchpoint["DhwState"]

        except IndexError:
            self._setpoints = {}
            _LOGGER.warning(
                "Failed to get setpoints - please report as an issue", exc_info=True
            )

        return self._setpoints

    async def _update_schedule(self) -> None:
        """Get the latest schedule."""
        if "DailySchedules" in self._schedule and not self._schedule["DailySchedules"]:
            if not self._evo_device.setpointStatus["setpointMode"] == EVO_FOLLOW:
                return  # avoid unnecessary I/O - there's nothing to update

        self._schedule = await self._call_client_api(
            self._evo_device.schedule(), refresh=False
        )

        _LOGGER.debug("Schedule['%s'] = %s", self.name, self._schedule)

    async def async_update(self) -> None:
        """Get the latest state data."""
        next_sp_from = self._setpoints.get("next_sp_from", "2000-01-01T00:00:00+00:00")
        if dt_util.now() >= dt_util.parse_datetime(next_sp_from):
            await self._update_schedule()  # no schedule, or it's out-of-date

        self._device_state_attrs = {"setpoints": self.setpoints}
