"""Proxy to handle account communication with Renault servers."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps
import logging
from typing import Any, Concatenate, ParamSpec, TypeVar, cast

from renault_api.exceptions import RenaultException
from renault_api.kamereon import models
from renault_api.renault_vehicle import RenaultVehicle

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .coordinator import RenaultDataUpdateCoordinator

LOGGER = logging.getLogger(__name__)
_T = TypeVar("_T")
_P = ParamSpec("_P")


def with_error_wrapping(
    func: Callable[Concatenate[RenaultVehicleProxy, _P], Awaitable[_T]],
) -> Callable[Concatenate[RenaultVehicleProxy, _P], Coroutine[Any, Any, _T]]:
    """Catch Renault errors."""

    @wraps(func)
    async def wrapper(
        self: RenaultVehicleProxy,
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> _T:
        """Catch RenaultException errors and raise HomeAssistantError."""
        try:
            return await func(self, *args, **kwargs)
        except RenaultException as err:
            raise HomeAssistantError(err) from err

    return wrapper


@dataclass
class RenaultCoordinatorDescription:
    """Class describing Renault coordinators."""

    endpoint: str
    key: str
    update_method: Callable[
        [RenaultVehicle],
        Callable[[], Awaitable[models.KamereonVehicleDataAttributes]],
    ]
    # Optional keys
    requires_electricity: bool = False


class RenaultVehicleProxy:
    """Handle vehicle communication with Renault servers."""

    def __init__(
        self,
        hass: HomeAssistant,
        vehicle: RenaultVehicle,
        details: models.KamereonVehicleDetails,
        scan_interval: timedelta,
    ) -> None:
        """Initialise vehicle proxy."""
        self.hass = hass
        self._vehicle = vehicle
        self._details = details
        self._device_info = DeviceInfo(
            identifiers={(DOMAIN, cast(str, details.vin))},
            manufacturer=(details.get_brand_label() or "").capitalize(),
            model=(details.get_model_label() or "").capitalize(),
            name=details.registrationNumber or "",
            sw_version=details.get_model_code() or "",
        )
        self.coordinators: dict[str, RenaultDataUpdateCoordinator] = {}
        self.hvac_target_temperature = 21
        self._scan_interval = scan_interval

    @property
    def details(self) -> models.KamereonVehicleDetails:
        """Return the specs of the vehicle."""
        return self._details

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return self._device_info

    async def async_initialise(self) -> None:
        """Load available coordinators."""
        self.coordinators = {
            coord.key: RenaultDataUpdateCoordinator(
                self.hass,
                LOGGER,
                # Name of the data. For logging purposes.
                name=f"{self.details.vin} {coord.key}",
                update_method=coord.update_method(self._vehicle),
                # Polling interval. Will only be polled if there are subscribers.
                update_interval=self._scan_interval,
            )
            for coord in COORDINATORS
            if (
                self.details.supports_endpoint(coord.endpoint)
                and (not coord.requires_electricity or self.details.uses_electricity())
            )
        }
        # Check all coordinators
        await asyncio.gather(
            *(
                coordinator.async_config_entry_first_refresh()
                for coordinator in self.coordinators.values()
            )
        )
        for key in list(self.coordinators):
            # list() to avoid Runtime iteration error
            coordinator = self.coordinators[key]
            if coordinator.not_supported:
                # Remove endpoint as it is not supported for this vehicle.
                LOGGER.warning(
                    "Ignoring endpoint %s as it is not supported: %s",
                    coordinator.name,
                    coordinator.last_exception,
                )
                del self.coordinators[key]
            elif coordinator.access_denied:
                # Remove endpoint as it is denied for this vehicle.
                LOGGER.warning(
                    "Ignoring endpoint %s as it is denied: %s",
                    coordinator.name,
                    coordinator.last_exception,
                )
                del self.coordinators[key]

    @with_error_wrapping
    async def set_charge_mode(
        self, charge_mode: str
    ) -> models.KamereonVehicleChargeModeActionData:
        """Set vehicle charge mode."""
        return await self._vehicle.set_charge_mode(charge_mode)

    @with_error_wrapping
    async def set_charge_start(self) -> models.KamereonVehicleChargingStartActionData:
        """Start vehicle charge."""
        return await self._vehicle.set_charge_start()

    @with_error_wrapping
    async def set_charge_stop(self) -> models.KamereonVehicleChargingStartActionData:
        """Stop vehicle charge."""
        return await self._vehicle.set_charge_stop()

    @with_error_wrapping
    async def set_ac_stop(self) -> models.KamereonVehicleHvacStartActionData:
        """Stop vehicle ac."""
        return await self._vehicle.set_ac_stop()

    @with_error_wrapping
    async def set_ac_start(
        self, temperature: float, when: datetime | None = None
    ) -> models.KamereonVehicleHvacStartActionData:
        """Start vehicle ac."""
        return await self._vehicle.set_ac_start(temperature, when)

    @with_error_wrapping
    async def get_charging_settings(self) -> models.KamereonVehicleChargingSettingsData:
        """Get vehicle charging settings."""
        return await self._vehicle.get_charging_settings()

    @with_error_wrapping
    async def set_charge_schedules(
        self, schedules: list[models.ChargeSchedule]
    ) -> models.KamereonVehicleChargeScheduleActionData:
        """Set vehicle charge schedules."""
        return await self._vehicle.set_charge_schedules(schedules)


COORDINATORS: tuple[RenaultCoordinatorDescription, ...] = (
    RenaultCoordinatorDescription(
        endpoint="cockpit",
        key="cockpit",
        update_method=lambda x: x.get_cockpit,
    ),
    RenaultCoordinatorDescription(
        endpoint="hvac-status",
        key="hvac_status",
        update_method=lambda x: x.get_hvac_status,
    ),
    RenaultCoordinatorDescription(
        endpoint="location",
        key="location",
        update_method=lambda x: x.get_location,
    ),
    RenaultCoordinatorDescription(
        endpoint="battery-status",
        key="battery",
        requires_electricity=True,
        update_method=lambda x: x.get_battery_status,
    ),
    RenaultCoordinatorDescription(
        endpoint="charge-mode",
        key="charge_mode",
        requires_electricity=True,
        update_method=lambda x: x.get_charge_mode,
    ),
    RenaultCoordinatorDescription(
        endpoint="lock-status",
        key="lock_status",
        update_method=lambda x: x.get_lock_status,
    ),
    RenaultCoordinatorDescription(
        endpoint="res-state",
        key="res_state",
        update_method=lambda x: x.get_res_state,
    ),
)
