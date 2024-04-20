"""Update platform for Tessie integration."""

from __future__ import annotations

from typing import Any

from tessie_api import schedule_software_update

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, TessieUpdateStatus
from .coordinator import TessieStateUpdateCoordinator
from .entity import TessieEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Tessie Update platform from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        TessieUpdateEntity(vehicle.state_coordinator) for vehicle in data
    )


class TessieUpdateEntity(TessieEntity, UpdateEntity):
    """Tessie Updates entity."""

    _attr_supported_features = UpdateEntityFeature.PROGRESS

    def __init__(
        self,
        coordinator: TessieStateUpdateCoordinator,
    ) -> None:
        """Initialize the Update."""
        super().__init__(coordinator, "update")

    @property
    def supported_features(self) -> UpdateEntityFeature:
        """Flag supported features."""
        if self.get("vehicle_state_software_update_status") in (
            TessieUpdateStatus.AVAILABLE,
            TessieUpdateStatus.SCHEDULED,
        ):
            return self._attr_supported_features | UpdateEntityFeature.INSTALL
        return self._attr_supported_features

    @property
    def installed_version(self) -> str:
        """Return the current app version."""
        # Discard build from version number
        return self.coordinator.data["vehicle_state_car_version"].split(" ")[0]

    @property
    def latest_version(self) -> str | None:
        """Return the latest version."""
        if self.get("vehicle_state_software_update_status") in (
            TessieUpdateStatus.AVAILABLE,
            TessieUpdateStatus.SCHEDULED,
            TessieUpdateStatus.INSTALLING,
            TessieUpdateStatus.DOWNLOADING,
            TessieUpdateStatus.WIFI_WAIT,
        ):
            return self.get("vehicle_state_software_update_version")
        return self.installed_version

    @property
    def in_progress(self) -> bool | int | None:
        """Update installation progress."""
        if (
            self.get("vehicle_state_software_update_status")
            == TessieUpdateStatus.INSTALLING
        ):
            return self.get("vehicle_state_software_update_install_perc")
        return False

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        await self.run(schedule_software_update, in_seconds=0)
        self.set(
            ("vehicle_state_software_update_status", TessieUpdateStatus.INSTALLING)
        )
