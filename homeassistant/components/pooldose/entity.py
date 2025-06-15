"""Base entity for Seko Pooldose integration."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity


class PooldoseEntity(CoordinatorEntity):
    """Base class for all Pooldose entities."""

    def __init__(
        self,
        coordinator,
        api,
        translation_key,
        uid,
        key,
        serialnumber,
        device_info_dict,
        enabled_by_default=True,
    ) -> None:
        """Initialize the base Pooldose entity."""
        super().__init__(coordinator)
        self._api = api
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{serialnumber}_{key}"
        self._key = key
        self._attr_device_info = device_info_dict
        self._attr_entity_registry_enabled_default = enabled_by_default
