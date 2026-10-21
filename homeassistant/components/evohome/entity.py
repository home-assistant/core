"""Support for entities of the Evohome integration."""

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
import logging
from typing import Any, override

import evohomeasync2 as evo
from evohomeasync2.const import (
    SZ_SINCE,
    SZ_TIME_UNTIL,
    SZ_UNTIL,
    ZoneModelType as EvoZoneModelType,
    ZoneType as EvoZoneType,
)

from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import EvoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def _recurse_and_revert(val: Any, _key: str | None = None) -> Any:
    """Recursively revert any values to native format."""
    if isinstance(val, dict):
        return {k: _recurse_and_revert(v, k) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return type(val)(_recurse_and_revert(v) for v in val)
    if isinstance(val, datetime) and _key in (SZ_SINCE, SZ_TIME_UNTIL, SZ_UNTIL):
        return val.isoformat()
    if isinstance(val, StrEnum):
        return "".join(word.capitalize() for word in val.value.split("_"))
    return val


def is_valid_zone(zone: evo.Zone) -> bool:
    """Check if an Evohome zone should have climate and button entities."""
    return (
        zone.model == EvoZoneModelType.HEATING_ZONE
        or zone.type == EvoZoneType.THERMOSTAT
    )


def unique_zone_id(evo_device: evo.Zone) -> str:
    """Return a unique identifier for a zone-based entity.

    Some systems assign the zone the same ID as its parent TCS; in that case
    we append 'z' so the zone entity doesn't collide with the controller entity.
    """
    if evo_device.id == evo_device.tcs.id:
        return f"{evo_device.id}z"
    return evo_device.id


class EvoEntity(CoordinatorEntity[EvoDataUpdateCoordinator]):
    """Base for Evohome's Climate & WaterHeater entities."""

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

    @property
    @override
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return the evohome-specific state attributes."""
        return {"status": self._device_state_attrs}

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        self._device_state_attrs[self._evo_id_attr] = self._evo_device.id

        for attr in self._evo_state_attr_names:
            self._device_state_attrs[attr] = getattr(self._evo_device, attr)

        self._device_state_attrs = _recurse_and_revert(self._device_state_attrs)

        super()._handle_coordinator_update()

    async def update_attrs(self) -> None:
        """Update the entity's extra state attrs."""
        self._handle_coordinator_update()


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

        self._evo_id = evo_device.id
        self._evo_tcs = evo_device.tcs

        self._setpoints: dict[str, Any] = {}

    @property
    def native_current_temperature(self) -> float | None:
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

        try:
            this_sp = self._evo_device.this_switchpoint
            next_sp = self._evo_device.next_switchpoint
        except evo.NotFetchedError, evo.InvalidScheduleError:
            return self._setpoints  # the coordinator has yet to fetch a valid schedule

        if this_sp is None or next_sp is None:  # there is no schedule
            return self._setpoints

        this_sp_dtm, this_sp_val = this_sp
        next_sp_dtm, next_sp_val = next_sp

        key = "temp" if isinstance(self._evo_device, evo.Zone) else "state"

        self._setpoints = {
            "this_sp_from": this_sp_dtm,
            f"this_sp_{key}": this_sp_val,
            "next_sp_from": next_sp_dtm,
            f"next_sp_{key}": next_sp_val,
        }

        return self._setpoints

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        self._device_state_attrs = {
            "activeFaults": self._evo_device.active_faults,
            "setpoints": self.setpoints,
        }

        super()._handle_coordinator_update()
