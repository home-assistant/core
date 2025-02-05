"""Component to control TOLO Sauna/Steam Bath."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ACCESSORIES, DOMAIN
from .coordinator import ToloSaunaUpdateCoordinator


class ToloSaunaCoordinatorEntity(CoordinatorEntity[ToloSaunaUpdateCoordinator]):
    """CoordinatorEntity for TOLO Sauna."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: ToloSaunaUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize ToloSaunaCoordinatorEntity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            name="TOLO Sauna",
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="SteamTec",
            model=self.coordinator.data.status.model.name.capitalize(),
        )


class ToloEntityDescription(EntityDescription, frozen_or_thawed=True):
    """Abstract EntityDescription class for TOLO Sauna."""

    accessory_required: str | None = None


def has_accessory(entry: ConfigEntry, accessory_required: str | None = None) -> bool:
    """Check accessory availability configuration."""

    # if no accessory is required, return True.
    if accessory_required is None:
        return True

    # If an accessory is required, check if it is configured.
    # If not explicitly disabled, return True.
    return bool(entry.data[CONF_ACCESSORIES].get(accessory_required, True))
