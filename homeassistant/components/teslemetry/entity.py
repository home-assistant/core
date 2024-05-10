"""Teslemetry parent entity class."""

import asyncio
from typing import Any

from tesla_fleet_api.exceptions import TeslaFleetError

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODELS, TeslemetryState
from .coordinator import (
    TeslemetryEnergyDataCoordinator,
    TeslemetryVehicleDataCoordinator,
)
from .models import TeslemetryEnergyData, TeslemetryVehicleData


class TeslemetryVehicleEntity(CoordinatorEntity[TeslemetryVehicleDataCoordinator]):
    """Parent class for Teslemetry Vehicle Entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        vehicle: TeslemetryVehicleData,
        key: str,
    ) -> None:
        """Initialize common aspects of a Teslemetry entity."""
        super().__init__(vehicle.coordinator)
        self.key = key
        self.api = vehicle.api
        self._wakelock = vehicle.wakelock

        car_type = self.coordinator.data["vehicle_config_car_type"]

        self._attr_translation_key = key
        self._attr_unique_id = f"{vehicle.vin}-{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vehicle.vin)},
            manufacturer="Tesla",
            configuration_url="https://teslemetry.com/console",
            name=self.coordinator.data["vehicle_state_vehicle_name"],
            model=MODELS.get(car_type, car_type),
            sw_version=self.coordinator.data["vehicle_state_car_version"].split(" ")[0],
            hw_version=self.coordinator.data["vehicle_config_driver_assist"],
            serial_number=vehicle.vin,
        )

    @property
    def _value(self) -> Any | None:
        """Return a specific value from coordinator data."""
        return self.coordinator.data.get(self.key)

    async def wake_up_if_asleep(self) -> None:
        """Wake up the vehicle if its asleep."""
        async with self._wakelock:
            times = 0
            while self.coordinator.data["state"] != TeslemetryState.ONLINE:
                try:
                    if times == 0:
                        cmd = await self.api.wake_up()
                    else:
                        cmd = await self.api.vehicle()
                    state = cmd["response"]["state"]
                except TeslaFleetError as e:
                    raise HomeAssistantError(str(e)) from e
                self.coordinator.data["state"] = state
                if state != TeslemetryState.ONLINE:
                    times += 1
                    if times >= 4:  # Give up after 30 seconds total
                        raise HomeAssistantError("Could not wake up vehicle")
                    await asyncio.sleep(times * 5)

    def get(self, key: str | None = None, default: Any | None = None) -> Any:
        """Return a specific value from coordinator data."""
        return self.coordinator.data.get(key or self.key, default)

    def set(self, *args: Any) -> None:
        """Set a value in coordinator data."""
        for key, value in args:
            self.coordinator.data[key] = value
        self.async_write_ha_state()

    def raise_for_scope(self):
        """Raise an error if a scope is not available."""
        if not self.scoped:
            raise ServiceValidationError("Missing required scope")


class TeslemetryEnergyEntity(CoordinatorEntity[TeslemetryEnergyDataCoordinator]):
    """Parent class for Teslemetry Energy Entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        energysite: TeslemetryEnergyData,
        key: str,
    ) -> None:
        """Initialize common aspects of a Teslemetry entity."""
        super().__init__(energysite.coordinator)
        self.key = key
        self.api = energysite.api

        self._attr_translation_key = key
        self._attr_unique_id = f"{energysite.id}-{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(energysite.id))},
            manufacturer="Tesla",
            configuration_url="https://teslemetry.com/console",
            name=self.coordinator.data.get("site_name", "Energy Site"),
        )

    def get(self, key: str | None = None, default: Any | None = None) -> Any:
        """Return a specific value from coordinator data."""
        return self.coordinator.data.get(key or self.key, default)


class TeslemetryWallConnectorEntity(CoordinatorEntity[TeslemetryEnergyDataCoordinator]):
    """Parent class for Teslemetry Wall Connector Entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        energysite: TeslemetryEnergyData,
        din: str,
        key: str,
    ) -> None:
        """Initialize common aspects of a Teslemetry entity."""
        super().__init__(energysite.coordinator)
        self.din = din
        self.key = key

        self._attr_translation_key = key
        self._attr_unique_id = f"{energysite.id}-{din}-{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, din)},
            manufacturer="Tesla",
            configuration_url="https://teslemetry.com/console",
            name="Wall Connector",
            via_device=(DOMAIN, str(energysite.id)),
            serial_number=din.split("-")[-1],
        )

    @property
    def _value(self) -> int:
        """Return a specific wall connector value from coordinator data."""
        return self.coordinator.data["wall_connectors"][self.din].get(self.key)
