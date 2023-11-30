"""The Stookwijzer integration entities."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import StookwijzerCoordinator


class StookwijzerEntity(CoordinatorEntity, Entity):
    """Base class for Stookwijzer entities."""

    _attr_attribution = "Data provided by atlasleefomgeving.nl"
    _attr_should_poll = False

    def __init__(
        self,
        description: EntityDescription,
        coordinator: StookwijzerCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize a Stookwijzer device."""

        self.entity_description = description
        super().__init__(coordinator)

        self._coordinator = coordinator
        self._attr_unique_id = DOMAIN + description.key
        self._attr_name = description.key.title()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=description.key,
            manufacturer="Atlas Leefomgeving",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://www.atlasleefomgeving.nl/stookwijzer",
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._coordinator.client.advice is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        if not self.entity_description.attr_fn:  # type: ignore[attr-defined]
            return None

        return {"forecast": self.entity_description.attr_fn(self._coordinator)}  # type: ignore[attr-defined]
