"""Base for evohome entity."""

from datetime import UTC, datetime
import logging
from typing import Any

import evohomeasync2 as evo
from evohomeasync2.const import (
    SZ_SETPOINT_STATUS,
    SZ_STATE_STATUS,
    SZ_SYSTEM_MODE_STATUS,
    SZ_TIME_UNTIL,
    SZ_UNTIL,
)

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import EvoService
from .const import DOMAIN
from .coordinator import EvoDataUpdateCoordinator
from .helpers import convert_dict, convert_until

_LOGGER = logging.getLogger(__name__)


class EvoDevice(Entity):
    """Base for any evohome-compatible entity (controller, DHW, zone).

    This includes the controller, (1 to 12) heating zones and (optionally) a
    DHW controller.
    """

    # self.schedule_update_ha_state()

    _attr_should_poll = False

    def __init__(
        self,
        evo_broker: EvoDataUpdateCoordinator,
        evo_device: evo.ControlSystem | evo.HotWater | evo.Zone,
    ) -> None:
        """Initialize an evohome-compatible entity (TCS, DHW, zone)."""
        self._evo_device = evo_device
        self._evo_broker = evo_broker

        self._device_state_attrs: dict[str, Any] = {}

    async def async_refresh(self, payload: dict | None = None) -> None:
        """Process any signals."""
        if payload is None:
            # force_refresh invokes self.async_update() before self.async_write_ha_state()
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

    _evo_device: evo.HotWater | evo.Zone
    _evo_id: str

    def __init__(
        self, evo_broker: EvoDataUpdateCoordinator, evo_device: evo.HotWater | evo.Zone
    ) -> None:
        """Initialize an evohome-compatible child entity (DHW, zone)."""
        super().__init__(evo_broker, evo_device)

        self._evo_tcs = evo_device.tcs

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

        return self._setpoints

    async def _update_schedule(self) -> None:
        """Get the latest schedule, if any."""

        try:
            schedule = await self._evo_broker.call_client_api(
                self._evo_device.get_schedule(),  # type: ignore[arg-type]
                update_state=False,
            )
        except evo.InvalidScheduleError as err:
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

        if not self._schedule:
            await self._update_schedule()

        if not self._schedule:
            self._device_state_attrs = {}
            return

        if self._evo_device.next_switchpoint[0] > datetime.now(tz=UTC):
            await self._update_schedule()  # no schedule, or it's out-of-date

        this_sp_dtm, this_sp_val = self._evo_device.this_switchpoint
        next_sp_dtm, next_sp_val = self._evo_device.next_switchpoint

        key = "temp" if isinstance(self._evo_device, evo.Zone) else "state"

        self._setpoints = {
            "this_sp_from": this_sp_dtm.isoformat(),
            f"this_sp_{key}": this_sp_val,
            "next_sp_from": next_sp_dtm.isoformat(),
            f"next_sp_{key}": next_sp_val,
        }

        self._device_state_attrs = {"setpoints": self.setpoints}
