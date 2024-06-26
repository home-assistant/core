"""Tessie parent entity class."""

from collections.abc import Awaitable, Callable
from typing import Any

from aiohttp import ClientResponseError

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TessieStateUpdateCoordinator
from .models import TessieVehicleData


class TessieEntity(CoordinatorEntity[TessieStateUpdateCoordinator]):
    """Parent class for Tessie Entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        vehicle: TessieVehicleData,
        key: str,
    ) -> None:
        """Initialize common aspects of a Tessie entity."""
        super().__init__(vehicle.data_coordinator)
        self.vin = vehicle.vin
        self.key = key

        self._attr_translation_key = key
        self._attr_unique_id = f"{vehicle.vin}-{key}"
        self._attr_device_info = vehicle.device

    @property
    def _value(self) -> Any:
        """Return value from coordinator data."""
        return self.coordinator.data.get(self.key)

    def get(self, key: str | None = None, default: Any | None = None) -> Any:
        """Return a specific value from coordinator data."""
        return self.coordinator.data.get(key or self.key, default)

    async def run(
        self, func: Callable[..., Awaitable[dict[str, Any]]], **kargs: Any
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
            name: str = getattr(self, "name", self.entity_id)
            reason: str = response.get("reason", "unknown")
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=reason.replace(" ", "_"),
                translation_placeholders={"name": name},
            )

    def set(self, *args: Any) -> None:
        """Set a value in coordinator data."""
        for key, value in args:
            self.coordinator.data[key] = value
        self.async_write_ha_state()
