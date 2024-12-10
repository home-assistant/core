"""Base class for entities."""

from ohme import OhmeApiClient

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import OhmeCoordinator


class OhmeEntity(CoordinatorEntity[OhmeCoordinator]):
    """Base class for all Ohme entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OhmeCoordinator,
        hass: HomeAssistant,
        client: OhmeApiClient,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        self.entity_description = entity_description
        self._attr_translation_key = entity_description.key
        self._attr_device_info = DeviceInfo(**client.get_device_info())

        self._hass = hass
        self._client = client

    @property
    def unique_id(self) -> str:
        """Return unique ID of the entity."""
        return f"{self._client.serial}_{self._attr_translation_key}"
