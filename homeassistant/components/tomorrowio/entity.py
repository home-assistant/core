"""The Tomorrow.io integration."""

from collections.abc import Mapping
from typing import Any

from pytomorrowio.const import CURRENT

from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, INTEGRATION_NAME
from .coordinator import TomorrowioConfigEntry, TomorrowioDataUpdateCoordinator


@callback
def async_get_base_unique_id(api_key: str, location: Mapping[str, Any]) -> str:
    """Return the base unique ID for a location.

    This must reproduce the unique ID of the pre-subentry config entries
    byte-for-byte so migrated entities keep their unique IDs.
    """
    return f"{api_key}_{location[CONF_LATITUDE]}_{location[CONF_LONGITUDE]}"


class TomorrowioEntity(CoordinatorEntity[TomorrowioDataUpdateCoordinator]):
    """Base Tomorrow.io Entity."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: TomorrowioConfigEntry,
        subentry: ConfigSubentry,
        coordinator: TomorrowioDataUpdateCoordinator,
        api_version: int,
    ) -> None:
        """Initialize Tomorrow.io Entity."""
        super().__init__(coordinator)
        self.api_version = api_version
        self._config_entry = config_entry
        self._subentry = subentry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer=INTEGRATION_NAME,
            sw_version=f"v{self.api_version}",
            entry_type=DeviceEntryType.SERVICE,
        )

    def _get_current_property(self, property_name: str) -> Any | None:
        """Get property from current conditions.

        Used for V4 API.
        """
        return (
            self.coordinator.data.get(self._subentry.subentry_id, {})
            .get(CURRENT, {})
            .get(property_name)
        )
