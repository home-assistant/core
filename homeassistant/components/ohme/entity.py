"""Base class for entities."""

from ohme import OhmeApiClient

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)


class OhmeEntity(CoordinatorEntity):
    """Base class for all Ohme entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        hass: HomeAssistant,
        client: OhmeApiClient,
    ):
        """Initialize the entity."""
        super().__init__(coordinator)
        self._hass = hass
        self._client = client

        self._attributes = {}
        self._last_updated = None
        self._state = None

        self._attr_device_info = client.get_device_info()

    @property
    def unique_id(self):
        """Return unique ID of the entity."""
        return f"{self._client.serial}_{self._attr_translation_key}"
