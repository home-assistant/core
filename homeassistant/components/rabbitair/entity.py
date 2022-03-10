"""A base class for Rabbit Air entities."""
from __future__ import annotations

import logging
from typing import Any, cast

from rabbitair import Model, State

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RabbitAirDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

MODELS = {
    Model.A3: "A3",
    Model.BioGS: "BioGS 2.0",
    Model.MinusA2: "MinusA2",
    None: None,
}


class RabbitAirBaseEntity(CoordinatorEntity[State]):
    """Base class for Rabbit Air entity."""

    def __init__(
        self,
        coordinator: RabbitAirDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = entry.title or "Rabbit Air"
        self._attr_unique_id = entry.unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},  # type: ignore[arg-type]
            manufacturer="Rabbit Air",
            model=MODELS.get(coordinator.data.model),
            name=entry.title,
            sw_version=coordinator.data.wifi_firmware,
            hw_version=coordinator.data.main_firmware,
        )

    def _is_model(self, model: Model | list[Model]) -> bool:
        """Check the model of the device."""
        if isinstance(model, list):
            return self.coordinator.data.model in model
        return self.coordinator.data.model is model

    async def _set_state(self, **kwargs: Any) -> None:
        """Change the state of the device."""
        _LOGGER.debug("Set state %s", kwargs)
        coordinator = cast(RabbitAirDataUpdateCoordinator, self.coordinator)
        await coordinator.device.set_state(**kwargs)
        # Force polling of the device, because changing one parameter often
        # causes other parameters to change as well. By getting updated status
        # we provide a better user experience, especially if the default
        # polling interval is set too long.
        await self.coordinator.async_request_refresh()
