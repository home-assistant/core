"""Base entity for Seko Pooldose integration."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity


class PooldoseEntity(CoordinatorEntity):
    """Base class for all Pooldose entities."""

    def __init__(
        self,
        coordinator,
        client,
        translation_key,
        key,
        serialnumber,
        device_info_dict,
        enabled_by_default,
    ) -> None:
        """Initialize the base Pooldose entity."""
        super().__init__(coordinator)
        self._client = client
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{serialnumber}_{key}"
        self._key = key
        self._attr_device_info = device_info_dict
        self._attr_entity_registry_enabled_default = enabled_by_default
        self._attr_has_entity_name = True
