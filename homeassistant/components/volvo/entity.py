"""Volvo entity classes."""

from dataclasses import dataclass

from volvocarsapi.models import VolvoCarsApiBaseModel

from homeassistant.core import callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_VIN, DOMAIN
from .coordinator import VolvoDataCoordinator


def get_unique_id(vin: str, key: str) -> str:
    """Get the unique ID."""
    return f"{DOMAIN}_{vin}_{key}".lower()


def value_to_translation_key(value: str) -> str:
    """Make sure the translation key is valid."""
    return value.lower()


@dataclass(frozen=True, kw_only=True)
class VolvoEntityDescription(EntityDescription):
    """Describes a Volvo entity."""

    api_field: str


class VolvoEntity(CoordinatorEntity[VolvoDataCoordinator]):
    """Volvo base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VolvoDataCoordinator,
        description: VolvoEntityDescription,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator)

        self.entity_description: VolvoEntityDescription = description

        self._attr_unique_id = get_unique_id(
            coordinator.config_entry.data[CONF_VIN], description.key
        )

        self._attr_device_info = coordinator.device

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        api_field = self.coordinator.get_api_field(self.entity_description.api_field)

        self._attr_available = super().available and api_field is not None
        self._update_state(api_field)

        super()._handle_coordinator_update()

    def _update_state(self, api_field: VolvoCarsApiBaseModel | None) -> None:
        pass
