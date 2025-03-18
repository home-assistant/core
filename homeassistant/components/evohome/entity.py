"""Base for evohome entity."""

from collections.abc import Mapping
from datetime import UTC, datetime
import logging
from typing import Any

import evohomeasync2 as evo
from evohomeasync2.schemas.typedefs import DayOfWeekDhwT

from homeassistant.core import callback
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

    _evo_device: evo.ControlSystem | evo.HotWater | evo.Zone
    _evo_id_attr: str
    _evo_state_attr_names: tuple[str, ...]

    def __init__(
        self,
        coordinator: EvoDataUpdateCoordinator,
        evo_device: evo.ControlSystem | evo.HotWater | evo.Zone,
    ) -> None:
        """Initialize an evohome-compatible entity (TCS, DHW, zone)."""
        super().__init__(coordinator, context=evo_device.id)
        self._evo_device = evo_device

        self._device_state_attrs: dict[str, Any] = {}

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

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return the evohome-specific state attributes."""
        return {"status": self._device_state_attrs}

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()

        async_dispatcher_connect(self.hass, DOMAIN, self.process_signal)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        self._device_state_attrs[self._evo_id_attr] = self._evo_device.id

        for attr in self._evo_state_attr_names:
            self._device_state_attrs[attr] = getattr(self._evo_device, attr)

        super()._handle_coordinator_update()


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

        self._schedule: list[DayOfWeekDhwT] | None = None
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
    def setpoints(self) -> Mapping[str, Any]:
        """Return the current/next setpoints from the schedule.

        Only Zones & DHW controllers (but not the TCS) can have schedules.
        """

        if not self._schedule:
            return self._setpoints

        this_sp_dtm, this_sp_val = self._evo_device.this_switchpoint
        next_sp_dtm, next_sp_val = self._evo_device.next_switchpoint

        key = "temp" if isinstance(self._evo_device, evo.Zone) else "state"

        self._setpoints = {
            "this_sp_from": this_sp_dtm,
            f"this_sp_{key}": this_sp_val,
            "next_sp_from": next_sp_dtm,
            f"next_sp_{key}": next_sp_val,
        }

        return self._setpoints

    async def _update_schedule(self, force_refresh: bool = False) -> None:
        """Get the latest schedule, if any."""

        async def get_schedule() -> None:
            try:
                schedule = await self.coordinator.call_client_api(
                    self._evo_device.get_schedule(),  # type: ignore[arg-type]
                    request_refresh=False,
                )
            except evo.InvalidScheduleError as err:
                _LOGGER.warning(
                    "%s: Unable to retrieve a valid schedule: %s",
                    self._evo_device,
                    err,
                )
                self._schedule = []
                return
            else:
                self._schedule = schedule  # type: ignore[assignment]

            _LOGGER.debug("Schedule['%s'] = %s", self.name, schedule)

        if (
            force_refresh
            or self._schedule is None
            or (
                (until := self._setpoints.get("next_sp_from")) is not None
                and until < datetime.now(UTC)
            )
        ):  # must use self._setpoints, not self.setpoints
            await get_schedule()

        _ = self.setpoints  # update the setpoints attr

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        self._device_state_attrs = {
            "activeFaults": self._evo_device.active_faults,
            "setpoints": self._setpoints,
        }

        super()._handle_coordinator_update()

    async def update_attrs(self) -> None:
        """Update the entity's extra state attrs."""
        await self._update_schedule()
        self._handle_coordinator_update()
