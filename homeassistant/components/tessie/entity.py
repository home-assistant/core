"""Tessie parent entity class."""

from collections.abc import Awaitable, Callable
from typing import Any

from aiohttp import ClientResponseError

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODELS
from .coordinator import TessieStateUpdateCoordinator


class TessieEntity(CoordinatorEntity[TessieStateUpdateCoordinator]):
    """Parent class for Tessie Entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TessieStateUpdateCoordinator,
        key: str,
    ) -> None:
        """Initialize common aspects of a Tessie entity."""
        super().__init__(coordinator)
        self.vin = coordinator.vin
        self.key = key

        car_type = coordinator.data["vehicle_config_car_type"]

        self._attr_translation_key = key
        self._attr_unique_id = f"{self.vin}-{key}"
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

    @property
    def _value(self) -> Any:
        """Return value from coordinator data."""
        return self.coordinator.data[self.key]

    def get(self, key: str | None = None, default: Any | None = None) -> Any:
        """Return a specific value from coordinator data."""
        return self.coordinator.data.get(key or self.key, default)

    async def run(
        self, func: Callable[..., Awaitable[dict[str, bool | str]]], **kargs: Any
    ) -> None:
        """Run a tessie_api function and handle exceptions."""
        try:
            response = await func(
                session=self.coordinator.session,
                vin=self.vin,
                api_key=self.coordinator.api_key,
                **kargs,
            )
        except ClientResponseError as e:
            raise HomeAssistantError from e
        if response["result"] is False:
            raise HomeAssistantError(
                response.get("reason", "An unknown issue occurred")
            )

    def set(self, *args: Any) -> None:
        """Set a value in coordinator data."""
        for key, value in args:
            self.coordinator.data[key] = value
        self.async_write_ha_state()
