"""Tessie parent entity class."""

from abc import abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

from aiohttp import ClientResponseError

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODELS
from .coordinator import (
    TessieEnergySiteInfoCoordinator,
    TessieEnergySiteLiveCoordinator,
    TessieStateUpdateCoordinator,
)
from .models import TessieEnergyData


class TessieBaseEntity(
    CoordinatorEntity[
        TessieStateUpdateCoordinator
        | TessieEnergySiteInfoCoordinator
        | TessieEnergySiteLiveCoordinator
    ]
):
    """Parent class for Tessie entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TessieStateUpdateCoordinator
        | TessieEnergySiteInfoCoordinator
        | TessieEnergySiteLiveCoordinator,
        key: str,
    ) -> None:
        """Initialize common aspects of a Tessie entity."""

        self.key = key
        self._attr_translation_key = key
        super().__init__(coordinator)

    @property
    def _value(self) -> Any:
        """Return value from coordinator data."""
        return self.coordinator.data.get(self.key)

    def get(self, key: str | None = None, default: Any | None = None) -> Any:
        """Return a specific value from coordinator data."""
        return self.coordinator.data.get(key or self.key, default)

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @abstractmethod
    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""


class TessieEntity(TessieBaseEntity):
    """Parent class for Tessie vehicle entities."""

    def __init__(
        self,
        coordinator: TessieStateUpdateCoordinator,
        key: str,
    ) -> None:
        """Initialize common aspects of a Tessie vehicle entity."""
        self.vin = coordinator.vin
        self._session = coordinator.session
        self._api_key = coordinator.api_key
        self._attr_unique_id = f"{self.vin}-{key}"
        car_type = coordinator.data["vehicle_config_car_type"]

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.vin)},
            manufacturer="Tesla",
            configuration_url="https://my.tessie.com/",
            name=coordinator.data["display_name"],
            model=MODELS.get(car_type, car_type),
            sw_version=coordinator.data["vehicle_state_car_version"].split(" ")[0],
            hw_version=coordinator.data["vehicle_config_driver_assist"],
            serial_number=self.vin,
        )

        super().__init__(coordinator, key)

    def set(self, *args: Any) -> None:
        """Set a value in coordinator data."""
        for key, value in args:
            self.coordinator.data[key] = value
        self.async_write_ha_state()

    async def run(
        self, func: Callable[..., Awaitable[dict[str, Any]]], **kargs: Any
    ) -> None:
        """Run a tessie_api function and handle exceptions."""
        try:
            response = await func(
                session=self._session,
                vin=self.vin,
                api_key=self._api_key,
                **kargs,
            )
        except ClientResponseError as e:
            raise HomeAssistantError from e
        if response["result"] is False:
            name: str = getattr(self, "name", self.entity_id)
            reason: str = response.get("reason", "unknown")
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=reason.replace(" ", "_"),
                translation_placeholders={"name": name},
            )

    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""
        # Not used in this class yet


class TessieEnergyEntity(TessieBaseEntity):
    """Parent class for Tessie energy site entities."""

    def __init__(
        self,
        data: TessieEnergyData,
        coordinator: TessieEnergySiteInfoCoordinator | TessieEnergySiteLiveCoordinator,
        key: str,
    ) -> None:
        """Initialize common aspects of a Tessie energy site entity."""

        self._attr_unique_id = f"{data.id}-{key}"
        self._attr_device_info = data.device

        super().__init__(coordinator, key)


class TessieWallConnectorEntity(TessieBaseEntity):
    """Parent class for Tessie wall connector entities."""

    def __init__(
        self,
        data: TessieEnergyData,
        din: str,
        key: str,
    ) -> None:
        """Initialize common aspects of a Teslemetry entity."""
        self.din = din
        self._attr_unique_id = f"{data.id}-{din}-{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, din)},
            manufacturer="Tesla",
            name="Wall Connector",
            via_device=(DOMAIN, str(data.id)),
            serial_number=din.split("-")[-1],
        )

        super().__init__(data.live_coordinator, key)

    @property
    def _value(self) -> int:
        """Return a specific wall connector value from coordinator data."""
        return (
            self.coordinator.data.get("wall_connectors", {})
            .get(self.din, {})
            .get(self.key)
        )
