"""A base class for Rabbit Air entities."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from rabbitair import Client, Model, State

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

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
        coordinator: DataUpdateCoordinator[State],
        client: Client,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._client = client
        self._entry = entry
        # Use assert to suppress the type warning. We always set a unique ID in
        # the config flow, so it should never be None.
        assert entry.unique_id is not None
        self._attr_unique_id = entry.unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
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
        await self._client.set_state(**kwargs)
        # Wait for the changes to be applied and for the device status to be
        # updated. Two seconds should be sufficient, since the internal cycle
        # of the device runs at one-second intervals.
        await asyncio.sleep(2)
        # Force polling of the device, because changing one parameter often
        # causes other parameters to change as well. By getting updated status
        # immediately we provide a better user experience, especially if the
        # default polling interval is set too long.
        await self.coordinator.async_refresh()

    @property
    def name(self) -> str | None:
        """Return the name of this entity, if any."""
        return self._entry.title or "RabbitAir"
