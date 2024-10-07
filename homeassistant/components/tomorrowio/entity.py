"""The Tomorrow.io integration."""

from __future__ import annotations

from pytomorrowio.const import CURRENT

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, INTEGRATION_NAME
from .coordinator import TomorrowioDataUpdateCoordinator


class TomorrowioEntity(CoordinatorEntity[TomorrowioDataUpdateCoordinator]):
    """Base Tomorrow.io Entity."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: TomorrowioDataUpdateCoordinator,
        api_version: int,
    ) -> None:
        """Initialize Tomorrow.io Entity."""
        super().__init__(coordinator)
        self.api_version = api_version
        self._config_entry = config_entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._config_entry.data[CONF_API_KEY])},
            manufacturer=INTEGRATION_NAME,
            sw_version=f"v{self.api_version}",
            entry_type=DeviceEntryType.SERVICE,
        )

    def _get_current_property(self, property_name: str) -> int | str | float | None:
        """Get property from current conditions.

        Used for V4 API.
        """
        entry_id = self._config_entry.entry_id
        return self.coordinator.data[entry_id].get(CURRENT, {}).get(property_name)
