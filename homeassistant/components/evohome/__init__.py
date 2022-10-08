"""Support for (EMEA/EU-based) Honeywell TCC climate systems.

Such systems include evohome, Round Thermostat, and others.
"""
from __future__ import annotations

from datetime import datetime as dt, timedelta
import logging
import re
from typing import Any

import aiohttp.client_exceptions
import evohomeasync
import evohomeasync2
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
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.service import verify_domain_control
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from .const import CONF_LOCATION_IDX, DOMAIN, GWS, STORAGE_KEY, STORAGE_VER, TCS
from .coordinator import (
    EvoBroker,
    EvoDataUpdateCoordinator,
    _contextualise_v2_exception,
)

_LOGGER = logging.getLogger(__name__)

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
        return (string[0]).lower() + re.sub(
            r"[A-Z]",
            lambda matched: f"_{matched.group(0).lower()}",  # type:ignore[str-bytes-safe]
            string[1:],
        )

    return {
        (convert_key(k) if isinstance(k, str) else k): (
            convert_dict(v) if isinstance(v, dict) else v
        )
        for k, v in dictionary.items()
    }


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Create a (EMEA/EU-based) Honeywell TCC system."""

    # conf = config.get(DOMAIN)
    # if conf is None:
    #     return bool(hass.config_entries.async_entries(DOMAIN))

    store = Store[dict[str, Any]](hass, STORAGE_VER, STORAGE_KEY)
    tokens, user_data = await EvoBroker.load_auth_tokens(store, config[DOMAIN])

    client_v2 = evohomeasync2.EvohomeClient(
        config[DOMAIN][CONF_USERNAME],
        config[DOMAIN][CONF_PASSWORD],
        **tokens,
        session=async_get_clientsession(hass),
    )

    try:
        await client_v2.login()
    except (aiohttp.ClientError, evohomeasync2.AuthenticationError) as err:
        _LOGGER.error(_contextualise_v2_exception(err))
        return False
    finally:
        config[DOMAIN][CONF_PASSWORD] = "REDACTED"

    loc_idx = config[DOMAIN][CONF_LOCATION_IDX]
    try:
        loc_config = client_v2.installation_info[loc_idx]
    except IndexError:
        _LOGGER.error(
            "Config error: '%s' = %s, but the valid range is 0-%s. "
            "Unable to continue. Fix any configuration errors and restart HA",
            CONF_LOCATION_IDX,
            loc_idx,
            len(client_v2.installation_info) - 1,
        )
        return False

    if _LOGGER.isEnabledFor(logging.DEBUG):
        _config: dict[str, Any] = {
            "locationInfo": {"timeZone": None},
            GWS: [{TCS: None}],
        }
        _config["locationInfo"]["timeZone"] = loc_config["locationInfo"]["timeZone"]
        _config[GWS][0][TCS] = loc_config[GWS][0][TCS]
        _LOGGER.debug("Config = %s", _config)

    client_v1 = evohomeasync.EvohomeClient(
        client_v2.username,
        client_v2.password,
        user_data=user_data,
        session=async_get_clientsession(hass),
    )

    coordinator = EvoDataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_interval=config[DOMAIN][CONF_SCAN_INTERVAL],
    )

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN]["broker"] = broker = EvoBroker(
        hass, client_v2, client_v1, store, coordinator, config[DOMAIN]
    )

    coordinator.update_method = broker.async_update
    await coordinator.async_config_entry_first_refresh()  # will save access tokens too

    hass.async_create_task(
        async_load_platform(hass, Platform.CLIMATE, DOMAIN, {}, config)
    )
    if broker.tcs.hotwater:
        hass.async_create_task(
            async_load_platform(hass, Platform.WATER_HEATER, DOMAIN, {}, config)
        )
    setup_service_functions(hass, broker)

    async_track_time_interval(
        hass, coordinator.async_request_refresh, config[DOMAIN][CONF_SCAN_INTERVAL]
    )

    return True


@callback
def setup_service_functions(hass: HomeAssistant, broker):
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
    modes = broker.config["allowedSystemModes"]

    # Not all systems support "AutoWithReset": register this handler only if required
    if [m["systemMode"] for m in modes if m["systemMode"] == "AutoWithReset"]:
        hass.services.async_register(DOMAIN, SVC_RESET_SYSTEM, set_system_mode)

    system_mode_schemas = []
    modes = [m for m in modes if m["systemMode"] != "AutoWithReset"]

    # Permanent-only modes will use this schema
    perm_modes = [m["systemMode"] for m in modes if not m["canBeTemporary"]]
    if perm_modes:  # any of: "Auto", "HeatingOff": permanent only
        schema = vol.Schema({vol.Required(ATTR_SYSTEM_MODE): vol.In(perm_modes)})
        system_mode_schemas.append(schema)

    modes = [m for m in modes if m["canBeTemporary"]]

    # These modes are set for a number of hours (or indefinitely): use this schema
    temp_modes = [m["systemMode"] for m in modes if m["timingMode"] == "Duration"]
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
    temp_modes = [m["systemMode"] for m in modes if m["timingMode"] == "Period"]
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
            schema=vol.Any(*system_mode_schemas),
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


class EvoDevice(CoordinatorEntity):
    """Base for any evohome device.

    This includes the Controller, (up to 12) Heating Zones and (optionally) a
    DHW controller.
    """

    def __init__(self, evo_broker, evo_device) -> None:
        """Initialize the evohome entity."""
        super().__init__(evo_broker.coordinator)

        self._evo_device = evo_device
        self._evo_broker = evo_broker
        self._evo_tcs = evo_broker.tcs

        self._device_state_attrs: dict[str, Any] = {}

    async def async_handle_signal(self, *, payload: dict) -> None:
        """Process any signals."""
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
        if "systemModeStatus" in status:
            convert_until(status["systemModeStatus"], "timeUntil")
        if "setpointStatus" in status:
            convert_until(status["setpointStatus"], "until")
        if "stateStatus" in status:
            convert_until(status["stateStatus"], "until")

        return {"status": convert_dict(status)}

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        async_dispatcher_connect(self.hass, DOMAIN, self.async_handle_signal)


class EvoChild(EvoDevice):
    """Base for any evohome child.

    This includes (up to 12) Heating Zones and (optionally) a DHW controller.
    """

    def __init__(self, evo_broker, evo_device) -> None:
        """Initialize a evohome Controller (hub)."""
        super().__init__(evo_broker, evo_device)
        self._schedule: dict[str, Any] = {}
        self._setpoints: dict[str, Any] = {}

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature of a Zone."""
        if (
            self._evo_broker.temps
            and self._evo_broker.temps[self._evo_device.zoneId] != 128
        ):
            return self._evo_broker.temps[self._evo_device.zoneId]

        if self._evo_device.temperatureStatus["isAvailable"]:
            return self._evo_device.temperatureStatus["temperature"]

        return None

    @property
    def setpoints(self) -> dict[str, Any]:
        """Return the current/next setpoints from the schedule.

        Only Zones & DHW controllers (but not the TCS) can have schedules.
        """

        def _dt_evo_to_aware(dt_naive: dt, utc_offset: timedelta) -> dt:
            dt_aware = dt_naive.replace(tzinfo=dt_util.UTC) - utc_offset
            return dt_util.as_local(dt_aware)

        if not self._schedule or not self._schedule.get("DailySchedules"):
            return {}  # no scheduled setpoints when {'DailySchedules': []}

        day_time = dt_util.now()
        day_of_week = day_time.weekday()  # for evohome, 0 is Monday
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

            for key, offset, idx in (
                ("this", this_sp_day, sp_idx),
                ("next", next_sp_day, (sp_idx + 1) * (1 - next_sp_day)),
            ):
                sp_date = (day_time + timedelta(days=offset)).strftime("%Y-%m-%d")
                day = self._schedule["DailySchedules"][(day_of_week + offset) % 7]
                switchpoint = day["Switchpoints"][idx]

                switchpoint_time_of_day = dt_util.parse_datetime(
                    f"{sp_date}T{switchpoint['TimeOfDay']}"
                )
                assert switchpoint_time_of_day
                dt_aware = _dt_evo_to_aware(
                    switchpoint_time_of_day, self._evo_broker.tcs_utc_offset
                )

                self._setpoints[f"{key}_sp_from"] = dt_aware.isoformat()
                try:
                    self._setpoints[f"{key}_sp_temp"] = switchpoint["heatSetpoint"]
                except KeyError:
                    self._setpoints[f"{key}_sp_state"] = switchpoint["DhwState"]

        except IndexError:
            self._setpoints = {}
            _LOGGER.warning(
                "Failed to get setpoints, report as an issue if this error persists",
                exc_info=True,
            )

        return self._setpoints

    @property
    def should_poll(self) -> bool:
        """Return True as entity has to be polled for state.

        Despite being a CoordinatorEntity, polling is necessary as each evohome child
        downloads it's own schedules when required.
        """
        return True

    async def _update_schedule(self) -> None:
        """Get the latest schedule, if any."""
        self._schedule = await self._evo_broker.call_client_api(
            self._evo_device.schedule(), update_state=False
        )

        _LOGGER.debug("Schedule['%s'] = %s", self.name, self._schedule)

    async def async_update(self) -> None:
        """Update the entity."""
        # Ignore update requests if the entity is disabled
        if not self.enabled or not self.available:
            return

        next_sp_from = self._setpoints.get("next_sp_from", "2000-01-01T00:00:00+00:00")
        next_sp_from_dt = dt_util.parse_datetime(next_sp_from)
        if next_sp_from_dt is None or dt_util.now() >= next_sp_from_dt:
            await self._update_schedule()  # no schedule, or it's out-of-date

        self._device_state_attrs = {"setpoints": self.setpoints}

        await self.coordinator.async_request_refresh()
