"""Base entity for Ouman EH-800."""

from ouman_eh_800_api import OumanEndpoint

from homeassistant.const import CONF_URL
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ENDPOINTS_DISABLED_BY_DEFAULT
from .coordinator import OumanEh800Coordinator


class OumanEh800Entity(CoordinatorEntity[OumanEh800Coordinator]):
    """Base entity for Ouman EH-800."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: OumanEh800Coordinator, endpoint: OumanEndpoint
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._endpoint: OumanEndpoint = endpoint

        assert coordinator.config_entry is not None
        entry_id = coordinator.config_entry.entry_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Ouman EH-800",
            manufacturer="Ouman",
            model="EH-800",
            configuration_url=coordinator.config_entry.data[CONF_URL],
        )
        self._attr_unique_id = f"{entry_id}_{endpoint.name}"
        self._attr_translation_key = endpoint.name
        self._attr_entity_registry_enabled_default = (
            endpoint not in ENDPOINTS_DISABLED_BY_DEFAULT
        )
