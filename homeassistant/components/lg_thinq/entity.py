"""Base class for ThinQ entities."""

from __future__ import annotations

from collections.abc import Coroutine
import logging
from typing import Any

from thinqconnect import ThinQAPIException
from thinqconnect.devices.const import Location
from thinqconnect.integration import PropertyState

from homeassistant.core import callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import COMPANY, DOMAIN
from .coordinator import DeviceDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

EMPTY_STATE = PropertyState()


class ThinQEntity(CoordinatorEntity[DeviceDataUpdateCoordinator]):
    """The base implementation of all lg thinq entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DeviceDataUpdateCoordinator,
        entity_description: EntityDescription,
        property_id: str,
    ) -> None:
        """Initialize an entity."""
        super().__init__(coordinator)

        self.entity_description = entity_description
        self.property_id = property_id
        self.location = self.coordinator.api.get_location_for_idx(self.property_id)

        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, coordinator.unique_id)},
            manufacturer=COMPANY,
            model=coordinator.api.device.model_name,
            name=coordinator.device_name,
        )
        self._attr_unique_id = f"{coordinator.unique_id}_{self.property_id}"
        if self.location is not None and self.location not in (
            Location.MAIN,
            Location.OVEN,
            coordinator.sub_id,
        ):
            self._attr_translation_placeholders = {"location": self.location}
            self._attr_translation_key = (
                f"{entity_description.translation_key}_for_location"
            )

    @property
    def data(self) -> PropertyState:
        """Return the state data of entity."""
        return self.coordinator.data.get(self.property_id, EMPTY_STATE)

    def _update_status(self) -> None:
        """Update status itself.

        All inherited classes can update their own status in here.
        """

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_status()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    async def async_call_api(self, target: Coroutine[Any, Any, Any]) -> None:
        """Call the given api and handle exception."""
        try:
            await target
        except ThinQAPIException as exc:
            raise ServiceValidationError(
                exc.message,
                translation_domain=DOMAIN,
                translation_key=exc.code,
            ) from exc
        finally:
            await self.coordinator.async_request_refresh()
