"""Base for evohome entity."""

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

import evohomeasync2 as evo
from evohomeasync2.schema.const import (
    SZ_HEAT_SETPOINT,
    SZ_SETPOINT_STATUS,
    SZ_STATE_STATUS,
    SZ_SYSTEM_MODE_STATUS,
    SZ_TIME_UNTIL,
    SZ_UNTIL,
)

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util

from . import EvoBroker, EvoService
from .const import DOMAIN
from .helpers import convert_dict, convert_until

_LOGGER = logging.getLogger(__name__)


class EvoDevice(Entity):
    """Base for any evohome-compatible entity (controller, DHW, zone).

    This includes the controller, (1 to 12) heating zones and (optionally) a
    DHW controller.
    """

    _attr_should_poll = False

    def __init__(
        self,
        evo_broker: EvoBroker,
        evo_device: evo.ControlSystem | evo.HotWater | evo.Zone,
    ) -> None:
        """Initialize an evohome-compatible entity (TCS, DHW, zone)."""
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
        if payload["service"] in (
            EvoService.SET_ZONE_OVERRIDE,
            EvoService.RESET_ZONE_OVERRIDE,
        ):
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
    """Base for any evohome-compatible child entity (DHW, zone).

    This includes (1 to 12) heating zones and (optionally) a DHW controller.
    """

    _evo_id: str  # mypy hint

    def __init__(
        self, evo_broker: EvoBroker, evo_device: evo.HotWater | evo.Zone
    ) -> None:
        """Initialize an evohome-compatible child entity (DHW, zone)."""
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

        # get dt in the same TZ as the TCS location, so we can compare schedule times
        day_time = dt_util.now().astimezone(timezone(self._evo_broker.loc_utc_offset))
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

            # Did this setpoint start yesterday? Does the next setpoint start tomorrow?
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
                    switchpoint_time_of_day, self._evo_broker.loc_utc_offset
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
            schedule = await self._evo_broker.call_client_api(
                self._evo_device.get_schedule(), update_state=False
            )
        except evo.InvalidSchedule as err:
            _LOGGER.warning(
                "%s: Unable to retrieve a valid schedule: %s",
                self._evo_device,
                err,
            )
            self._schedule = {}
        else:
            self._schedule = schedule or {}

        _LOGGER.debug("Schedule['%s'] = %s", self.name, self._schedule)

    async def async_update(self) -> None:
        """Get the latest state data."""
        next_sp_from = self._setpoints.get("next_sp_from", "2000-01-01T00:00:00+00:00")
        next_sp_from_dt = dt_util.parse_datetime(next_sp_from)
        if next_sp_from_dt is None or dt_util.now() >= next_sp_from_dt:
            await self._update_schedule()  # no schedule, or it's out-of-date

        self._device_state_attrs = {"setpoints": self.setpoints}
