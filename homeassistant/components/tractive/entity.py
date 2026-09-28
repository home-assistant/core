"""A entity class for Tractive integration."""

from typing import Any

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TractiveCoordinator


class TractiveEntity(CoordinatorEntity[TractiveCoordinator]):
    """Tractive entity class."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TractiveCoordinator,
        trackable: dict[str, Any],
        tracker_details: dict[str, Any],
        hardware_entity: bool = True,
    ) -> None:
        """Initialize tracker entity."""
        super().__init__(coordinator)
        self._pet_id = trackable["_id"]
        self._tracker_id = tracker_details["_id"]
        if hardware_entity:
            self._attr_device_info = DeviceInfo(
                configuration_url="https://my.tractive.com/",
                identifiers={(DOMAIN, tracker_details["_id"])},
                translation_key="tracker",
                translation_placeholders={"id": tracker_details["_id"]},
                manufacturer="Tractive GmbH",
                sw_version=tracker_details["fw_version"],
                model_id=tracker_details["model_number"],
            )
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, trackable["_id"])},
                name=trackable["details"]["name"],
                via_device_id=dr.async_get_device_id_by_identifier(
                    coordinator.hass,
                    (DOMAIN, tracker_details["_id"]),
                    config_entry_id=coordinator.config_entry.entry_id,
                ),
                entry_type=DeviceEntryType.SERVICE,
            )
