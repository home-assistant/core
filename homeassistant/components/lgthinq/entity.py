"""Base class for ThinQ entities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from thinqconnect import ThinQAPIErrorCodes, ThinQAPIException
from thinqconnect.integration.homeassistant.property import Property as ThinQProperty

from homeassistant.core import callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DeviceDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True)
class PropertyInfo:
    """A data class contains an information for creating property."""

    # The property key for use in SDK must be snake_case string.
    key: str

    # Optional, if the value should be converted before calling api.
    value_converter: Callable[[Any], Any] | None = None


@dataclass(kw_only=True, frozen=True)
class ThinQEntityDescription(EntityDescription):
    """The base thinq entity description."""

    property_info: PropertyInfo


class ThinQEntity(CoordinatorEntity[DeviceDataUpdateCoordinator]):
    """The base implementation of all lg thinq entities."""

    _attr_has_entity_name = True
    entity_description: ThinQEntityDescription

    def __init__(
        self,
        coordinator: DeviceDataUpdateCoordinator,
        entity_description: ThinQEntityDescription,
        property: ThinQProperty,
    ) -> None:
        """Initialize an entity."""
        super().__init__(coordinator)

        self.entity_description = entity_description
        self._property = property
        self._attr_device_info = coordinator.device_info

        # Set the unique key. If there exist a location, add the prefix location name.
        unique_key = (
            f"{entity_description.key}"
            if property.location is None
            else f"{property.location}_{entity_description.key}"
        )
        self._attr_unique_id = f"{coordinator.unique_id}_{unique_key}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.is_connected

    def get_property(self) -> ThinQProperty | None:
        """Return the property corresponding to the feature."""
        return self._property

    def get_value_as_bool(self) -> bool:
        """Return the property value of entity as bool."""
        prop = self.get_property()
        return prop.get_value_as_bool() if prop is not None else False

    async def async_post_value(self, value: Any) -> None:
        """Post the value of entity to server."""
        prop = self.get_property()
        if prop is None:
            return

        try:
            await prop.async_post_value(value)
        except ThinQAPIException as exc:
            if exc.code == ThinQAPIErrorCodes.NOT_CONNECTED_DEVICE:
                self.coordinator.is_connected = False

            # Rollback device's status data.
            self.coordinator.async_set_updated_data({})

            raise ServiceValidationError(
                exc.message,
                translation_domain=DOMAIN,
                translation_key=exc.code,
            ) from exc

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
