"""Base for evohome entity."""

from datetime import UTC, datetime
import logging
from typing import Any

import evohomeasync2 as evo
from evohomeasync2.const import SZ_ACTIVE_FAULTS

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, EvoService
from .coordinator import EvoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class EvoEntity(CoordinatorEntity[EvoDataUpdateCoordinator]):
    """Base for any evohome-compatible entity (controller, DHW, zone).

    This includes the controller, (1 to 12) heating zones and (optionally) a
    DHW controller.
    """

    coordinator: EvoDataUpdateCoordinator

    _evo_device: evo.ControlSystem | evo.HotWater | evo.Zone
    _evo_id_attr: str

    def __init__(
        self,
        coordinator: EvoDataUpdateCoordinator,
        evo_device: evo.ControlSystem | evo.HotWater | evo.Zone,
    ) -> None:
        """Initialize an evohome-compatible entity (TCS, DHW, zone)."""
        super().__init__(coordinator)
        self._evo_device = evo_device

        self._attr_extra_state_attributes: dict[str, Any] = {}

    async def process_signal(self, payload: dict | None = None) -> None:
        """Process any signals."""

        if payload is None:
            raise NotImplementedError
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

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()

        async_dispatcher_connect(self.hass, DOMAIN, self.process_signal)

    async def async_update(self) -> None:
        """Get the latest state data."""
        await super().async_update()

        self._attr_extra_state_attributes = {self._evo_id_attr: self._evo_device.id}


class EvoChild(EvoEntity):
    """Base for any evohome-compatible child entity (DHW, zone).

    This includes (1 to 12) heating zones and (optionally) a DHW controller.
    """

    _evo_device: evo.HotWater | evo.Zone
    _evo_id: str

    def __init__(
        self, coordinator: EvoDataUpdateCoordinator, evo_device: evo.HotWater | evo.Zone
    ) -> None:
        """Initialize an evohome-compatible child entity (DHW, zone)."""
        super().__init__(coordinator, evo_device)

        self._evo_tcs = evo_device.tcs

        self._schedule: dict[str, Any] = {}
        self._setpoints: dict[str, Any] = {}

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature of a Zone."""

        assert isinstance(self._evo_device, evo.HotWater | evo.Zone)  # mypy check

        if (temp := self.coordinator.temps.get(self._evo_id)) is not None:
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
            schedule = await self.coordinator.call_client_api(
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
        await super().async_update()

        self._attr_extra_state_attributes[SZ_ACTIVE_FAULTS] = (
            self._evo_device.active_faults
        )

        if not self._schedule:
            await self._update_schedule()

            if not self._schedule:  # some systems have no schedule
                self._attr_extra_state_attributes["setpoints"] = {}
                return

        elif self._evo_device.next_switchpoint[0] < datetime.now(tz=UTC):
            await self._update_schedule()

        this_sp_dtm, this_sp_val = self._evo_device.this_switchpoint
        next_sp_dtm, next_sp_val = self._evo_device.next_switchpoint

        key = "temp" if isinstance(self._evo_device, evo.Zone) else "state"

        self._setpoints = {
            "this_sp_from": this_sp_dtm.isoformat(),
            f"this_sp_{key}": this_sp_val,
            "next_sp_from": next_sp_dtm.isoformat(),
            f"next_sp_{key}": next_sp_val,
        }

        self._attr_extra_state_attributes["setpoints"] = self.setpoints
