"""Teslemetry parent entity class."""

from abc import abstractmethod
import asyncio
from typing import Any

from tesla_fleet_api import EnergySpecific, VehicleSpecific
from tesla_fleet_api.exceptions import TeslaFleetError

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER, TeslemetryState
from .coordinator import (
    TeslemetryEnergySiteInfoCoordinator,
    TeslemetryEnergySiteLiveCoordinator,
    TeslemetryVehicleDataCoordinator,
)
from .models import TeslemetryEnergyData, TeslemetryVehicleData


class TeslemetryEntity(
    CoordinatorEntity[
        TeslemetryVehicleDataCoordinator
        | TeslemetryEnergySiteLiveCoordinator
        | TeslemetryEnergySiteInfoCoordinator
    ]
):
    """Parent class for all Teslemetry entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TeslemetryVehicleDataCoordinator
        | TeslemetryEnergySiteLiveCoordinator
        | TeslemetryEnergySiteInfoCoordinator,
        api: VehicleSpecific | EnergySpecific,
        key: str,
    ) -> None:
        """Initialize common aspects of a Teslemetry entity."""
        super().__init__(coordinator)
        self.api = api
        self.key = key
        self._attr_translation_key = self.key
        self._async_update_attrs()

    @property
    def available(self) -> bool:
        """Return if sensor is available."""
        return self.coordinator.last_update_success and self._attr_available

    @property
    def _value(self) -> Any | None:
        """Return a specific value from coordinator data."""
        return self.coordinator.data.get(self.key)

    def get(self, key: str, default: Any | None = None) -> Any | None:
        """Return a specific value from coordinator data."""
        return self.coordinator.data.get(key, default)

    @property
    def is_none(self) -> bool:
        """Return if the value is a literal None."""
        return self.get(self.key, False) is None

    @property
    def has(self) -> bool:
        """Return True if a specific value is in coordinator data."""
        return self.key in self.coordinator.data

    async def handle_command(self, command) -> dict[str, Any]:
        """Handle a command."""
        try:
            result = await command
        except TeslaFleetError as e:
            raise HomeAssistantError(f"Teslemetry command failed, {e.message}") from e
        LOGGER.debug("Command result: %s", result)
        return result

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        self.async_write_ha_state()

    @abstractmethod
    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""

    def raise_for_scope(self):
        """Raise an error if a scope is not available."""
        if not self.scoped:
            raise ServiceValidationError("Missing required scope")


class TeslemetryVehicleEntity(TeslemetryEntity):
    """Parent class for Teslemetry Vehicle entities."""

    _last_update: int = 0

    def __init__(
        self,
        data: TeslemetryVehicleData,
        key: str,
    ) -> None:
        """Initialize common aspects of a Teslemetry entity."""

        self._attr_unique_id = f"{data.vin}-{key}"
        self._wakelock = data.wakelock

        self._attr_device_info = data.device
        super().__init__(data.coordinator, data.api, key)

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

    async def handle_command(self, command) -> dict[str, Any]:
        """Handle a vehicle command."""
        result = await super().handle_command(command)
        if (response := result.get("response")) is None:
            if error := result.get("error"):
                # No response with error
                raise HomeAssistantError(error)
            # No response without error (unexpected)
            raise HomeAssistantError(f"Unknown response: {response}")
        if (result := response.get("result")) is not True:
            if reason := response.get("reason"):
                if reason in ("already_set", "not_charging", "requested"):
                    # Reason is acceptable
                    return result
                # Result of false with reason
                raise HomeAssistantError(reason)
            # Result of false without reason (unexpected)
            raise HomeAssistantError("Command failed with no reason")
        # Response with result of true
        return result


class TeslemetryEnergyLiveEntity(TeslemetryEntity):
    """Parent class for Teslemetry Energy Site Live entities."""

    def __init__(
        self,
        data: TeslemetryEnergyData,
        key: str,
    ) -> None:
        """Initialize common aspects of a Teslemetry Energy Site Live entity."""
        self._attr_unique_id = f"{data.id}-{key}"
        self._attr_device_info = data.device

        super().__init__(data.live_coordinator, data.api, key)


class TeslemetryEnergyInfoEntity(TeslemetryEntity):
    """Parent class for Teslemetry Energy Site Info Entities."""

    def __init__(
        self,
        data: TeslemetryEnergyData,
        key: str,
    ) -> None:
        """Initialize common aspects of a Teslemetry Energy Site Info entity."""
        self._attr_unique_id = f"{data.id}-{key}"
        self._attr_device_info = data.device

        super().__init__(data.info_coordinator, data.api, key)


class TeslemetryWallConnectorEntity(
    TeslemetryEntity, CoordinatorEntity[TeslemetryEnergySiteLiveCoordinator]
):
    """Parent class for Teslemetry Wall Connector Entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        data: TeslemetryEnergyData,
        din: str,
        key: str,
    ) -> None:
        """Initialize common aspects of a Teslemetry entity."""
        self.din = din
        self._attr_unique_id = f"{data.id}-{din}-{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, din)},
            manufacturer="Tesla",
            configuration_url="https://teslemetry.com/console",
            name="Wall Connector",
            via_device=(DOMAIN, str(data.id)),
            serial_number=din.split("-")[-1],
        )

        super().__init__(data.live_coordinator, data.api, key)

    @property
    def _value(self) -> int:
        """Return a specific wall connector value from coordinator data."""
        return (
            self.coordinator.data.get("wall_connectors", {})
            .get(self.din, {})
            .get(self.key)
        )
