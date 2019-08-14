"""Support for (EMEA/EU-based) Honeywell TCC climate systems.

Such systems include evohome (multi-zone), and Round Thermostat (single zone).
"""
import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any, Dict, Optional, Tuple

import requests.exceptions
import voluptuous as vol
import evohomeclient2

from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    HTTP_SERVICE_UNAVAILABLE,
    HTTP_TOO_MANY_REQUESTS,
    TEMP_CELSIUS,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    track_time_interval,
)
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.util.dt import parse_datetime, utcnow

from .const import DOMAIN, STORAGE_VERSION, STORAGE_KEY, GWS, TCS

_LOGGER = logging.getLogger(__name__)

CONF_ACCESS_TOKEN_EXPIRES = "access_token_expires"
CONF_REFRESH_TOKEN = "refresh_token"

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


def _local_dt_to_utc(dt_naive: datetime) -> datetime:
    dt_aware = utcnow() + (dt_naive - datetime.now())
    if dt_aware.microsecond >= 500000:
        dt_aware += timedelta(seconds=1)
    return dt_aware.replace(microsecond=0)


def _utc_to_local_dt(dt_aware: datetime) -> datetime:
    dt_naive = datetime.now() + (dt_aware - utcnow())
    if dt_naive.microsecond >= 500000:
        dt_naive += timedelta(seconds=1)
    return dt_naive.replace(microsecond=0)


def _handle_exception(err) -> bool:
    try:
        raise err

    except evohomeclient2.AuthenticationError:
        _LOGGER.error(
            "Failed to (re)authenticate with the vendor's server. "
            "Check that your username and password are correct. "
            "Message is: %s",
            err,
        )
        return False

    except requests.exceptions.ConnectionError:
        # this appears to be common with Honeywell's servers
        _LOGGER.warning(
            "Unable to connect with the vendor's server. "
            "Check your network and the vendor's status page."
            "Message is: %s",
            err,
        )
        return False

    except requests.exceptions.HTTPError:
        if err.response.status_code == HTTP_SERVICE_UNAVAILABLE:
            _LOGGER.warning(
                "Vendor says their server is currently unavailable. "
                "Check the vendor's status page."
            )
            return False

        if err.response.status_code == HTTP_TOO_MANY_REQUESTS:
            _LOGGER.warning(
                "The vendor's API rate limit has been exceeded. "
                "Consider increasing the %s.",
                CONF_SCAN_INTERVAL,
            )
            return False

        raise  # we don't expect/handle any other HTTPErrors


def setup(hass: HomeAssistantType, hass_config: ConfigType) -> bool:
    """Create a (EMEA/EU-based) Honeywell evohome system."""
    broker = EvoBroker(hass, hass_config[DOMAIN])
    if not broker.init_client():
        return False

    load_platform(hass, "climate", DOMAIN, {}, hass_config)
    if broker.tcs.hotwater:
        load_platform(hass, "water_heater", DOMAIN, {}, hass_config)

    track_time_interval(hass, broker.update, hass_config[DOMAIN][CONF_SCAN_INTERVAL])

    return True


class EvoBroker:
    """Container for evohome client and data."""

    def __init__(self, hass, params) -> None:
        """Initialize the evohome client and data structure."""
        self.hass = hass
        self.params = params

        self.config = self.status = self.timers = {}

        self.client = self.tcs = None
        self._app_storage = {}

        hass.data[DOMAIN] = {}
        hass.data[DOMAIN]["broker"] = self

    def init_client(self) -> bool:
        """Initialse the evohome data broker.

        Return True if this is successful, otherwise return False.
        """
        refresh_token, access_token, access_token_expires = asyncio.run_coroutine_threadsafe(
            self._load_auth_tokens(), self.hass.loop
        ).result()

        # evohomeclient2 uses naive/local datetimes
        if access_token_expires is not None:
            access_token_expires = _utc_to_local_dt(access_token_expires)

        try:
            client = self.client = evohomeclient2.EvohomeClient(
                self.params[CONF_USERNAME],
                self.params[CONF_PASSWORD],
                refresh_token=refresh_token,
                access_token=access_token,
                access_token_expires=access_token_expires,
            )

        except (
            requests.exceptions.RequestException,
            evohomeclient2.AuthenticationError,
        ) as err:
            if not _handle_exception(err):
                return False

        finally:
            self.params[CONF_PASSWORD] = "REDACTED"

        self.hass.add_job(self._save_auth_tokens())

        loc_idx = self.params[CONF_LOCATION_IDX]
        try:
            self.config = client.installation_info[loc_idx][GWS][0][TCS][0]

        except IndexError:
            _LOGGER.error(
                "Config error: '%s' = %s, but its valid range is 0-%s. "
                "Unable to continue. "
                "Fix any configuration errors and restart HA.",
                CONF_LOCATION_IDX,
                loc_idx,
                len(client.installation_info) - 1,
            )
            return False

        self.tcs = (
            client.locations[loc_idx]  # noqa: E501; pylint: disable=protected-access
            ._gateways[0]
            ._control_systems[0]
        )

        _LOGGER.debug("Config = %s", self.config)
        if _LOGGER.isEnabledFor(logging.DEBUG):
            # don't do an I/O unless required
            _LOGGER.debug(
                "Status = %s", client.locations[loc_idx].status()[GWS][0][TCS][0]
            )

        return True

    async def _load_auth_tokens(
        self
    ) -> Tuple[Optional[str], Optional[str], Optional[datetime]]:
        store = self.hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
        app_storage = self._app_storage = await store.async_load()

        if app_storage is None:
            app_storage = self._app_storage = {}

        if app_storage.get(CONF_USERNAME) == self.params[CONF_USERNAME]:
            refresh_token = app_storage.get(CONF_REFRESH_TOKEN)
            access_token = app_storage.get(CONF_ACCESS_TOKEN)
            at_expires_str = app_storage.get(CONF_ACCESS_TOKEN_EXPIRES)
            if at_expires_str:
                at_expires_dt = parse_datetime(at_expires_str)
            else:
                at_expires_dt = None

            return (refresh_token, access_token, at_expires_dt)

        return (None, None, None)  # account switched: so tokens wont be valid

    async def _save_auth_tokens(self, *args) -> None:
        # evohomeclient2 uses naive/local datetimes
        access_token_expires = _local_dt_to_utc(self.client.access_token_expires)

        self._app_storage[CONF_USERNAME] = self.params[CONF_USERNAME]
        self._app_storage[CONF_REFRESH_TOKEN] = self.client.refresh_token
        self._app_storage[CONF_ACCESS_TOKEN] = self.client.access_token
        self._app_storage[CONF_ACCESS_TOKEN_EXPIRES] = access_token_expires.isoformat()

        store = self.hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
        await store.async_save(self._app_storage)

        async_track_point_in_utc_time(
            self.hass,
            self._save_auth_tokens,
            access_token_expires + self.params[CONF_SCAN_INTERVAL],
        )

    def update(self, *args, **kwargs) -> None:
        """Get the latest state data of the entire evohome Location.

        This includes state data for the Controller and all its child devices,
        such as the operating mode of the Controller and the current temp of
        its children (e.g. Zones, DHW controller).
        """
        loc_idx = self.params[CONF_LOCATION_IDX]

        try:
            status = self.client.locations[loc_idx].status()[GWS][0][TCS][0]
        except (
            requests.exceptions.RequestException,
            evohomeclient2.AuthenticationError,
        ) as err:
            _handle_exception(err)
        else:
            self.timers["statusUpdated"] = utcnow()

        _LOGGER.debug("Status = %s", status)

        # inform the evohome devices that state data has been updated
        async_dispatcher_send(self.hass, DOMAIN, {"signal": "refresh"})


class EvoDevice(Entity):
    """Base for any evohome device.

    This includes the Controller, (up to 12) Heating Zones and
    (optionally) a DHW controller.
    """

    def __init__(self, evo_broker, evo_device) -> None:
        """Initialize the evohome entity."""
        self._evo_device = evo_device
        self._evo_tcs = evo_broker.tcs

        self._name = self._icon = self._precision = None
        self._state_attributes = []

        self._supported_features = None
        self._schedule = {}

    @callback
    def _refresh(self, packet):
        if packet["signal"] == "refresh":
            self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def setpoints(self) -> Dict[str, Any]:
        """Return the current/next setpoints from the schedule.

        Only Zones & DHW controllers (but not the TCS) can have schedules.
        """
        if not self._schedule["DailySchedules"]:
            return {}

        switchpoints = {}

        day_time = datetime.now()
        day_of_week = int(day_time.strftime("%w"))  # 0 is Sunday

        # Iterate today's switchpoints until past the current time of day...
        day = self._schedule["DailySchedules"][day_of_week]
        sp_idx = -1  # last switchpoint of the day before
        for i, tmp in enumerate(day["Switchpoints"]):
            if day_time.strftime("%H:%M:%S") > tmp["TimeOfDay"]:
                sp_idx = i  # current setpoint
            else:
                break

        # Did the current SP start yesterday? Does the next start SP tomorrow?
        current_sp_day = -1 if sp_idx == -1 else 0
        next_sp_day = 1 if sp_idx + 1 == len(day["Switchpoints"]) else 0

        for key, offset, idx in [
            ("current", current_sp_day, sp_idx),
            ("next", next_sp_day, (sp_idx + 1) * (1 - next_sp_day)),
        ]:

            spt = switchpoints[key] = {}

            sp_date = (day_time + timedelta(days=offset)).strftime("%Y-%m-%d")
            day = self._schedule["DailySchedules"][(day_of_week + offset) % 7]
            switchpoint = day["Switchpoints"][idx]

            dt_naive = datetime.strptime(
                "{}T{}".format(sp_date, switchpoint["TimeOfDay"]), "%Y-%m-%dT%H:%M:%S"
            )

            spt["from"] = _local_dt_to_utc(dt_naive).isoformat()
            try:
                spt["temperature"] = switchpoint["heatSetpoint"]
            except KeyError:
                spt["state"] = switchpoint["DhwState"]

        return switchpoints

    @property
    def should_poll(self) -> bool:
        """Evohome entities should not be polled."""
        return False

    @property
    def name(self) -> str:
        """Return the name of the Evohome entity."""
        return self._name

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the Evohome-specific state attributes."""
        status = {}
        for attr in self._state_attributes:
            if attr != "setpoints":
                status[attr] = getattr(self._evo_device, attr)

        if "setpoints" in self._state_attributes:
            status["setpoints"] = self.setpoints

        return {"status": status}

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
        async_dispatcher_connect(self.hass, DOMAIN, self._refresh)

    @property
    def precision(self) -> float:
        """Return the temperature precision to use in the frontend UI."""
        return self._precision

    @property
    def temperature_unit(self) -> str:
        """Return the temperature unit to use in the frontend UI."""
        return TEMP_CELSIUS

    def _update_schedule(self) -> None:
        """Get the latest state data."""
        if (
            not self._schedule.get("DailySchedules")
            or parse_datetime(self.setpoints["next"]["from"]) < utcnow()
        ):
            self._schedule = self._evo_device.schedule()

    def update(self) -> None:
        """Get the latest state data."""
        self._update_schedule()
