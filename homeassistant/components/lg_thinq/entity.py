"""Base class for ThinQ entities."""

from __future__ import annotations

import logging
from typing import Any

from thinqconnect import ThinQAPIException
from thinqconnect.integration.homeassistant.property import Property as ThinQProperty

from homeassistant.core import callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import COMPANY, DOMAIN
from .coordinator import DeviceDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class ThinQEntity(CoordinatorEntity[DeviceDataUpdateCoordinator]):
    """The base implementation of all lg thinq entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DeviceDataUpdateCoordinator,
        entity_description: EntityDescription,
        property: ThinQProperty,
    ) -> None:
        """Initialize an entity."""
        super().__init__(coordinator)

        self.entity_description = entity_description
        self.property = property
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, coordinator.unique_id)},
            manufacturer=COMPANY,
            model=coordinator.device_api.model_name,
            name=coordinator.device_name,
        )

        # Set the unique key. If there exist a location, add the prefix location name.
        unique_key = (
            f"{entity_description.key}"
            if property.location is None
            else f"{property.location}_{entity_description.key}"
        )
        self._attr_unique_id = f"{coordinator.unique_id}_{unique_key}"

        # Update initial status.
        self._update_status()

    async def async_post_value(self, value: Any) -> None:
        """Post the value of entity to server."""
        try:
            await self.property.async_post_value(value)
        except ThinQAPIException as exc:
            raise ServiceValidationError(
                exc.message,
                translation_domain=DOMAIN,
                translation_key=exc.code,
            ) from exc
        finally:
            await self.coordinator.async_request_refresh()

    def _update_status(self) -> None:
        """Update status itself.

        All inherited classes can update their own status in here.
        """

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_status()
        self.async_write_ha_state()
