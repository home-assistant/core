"""Update platform for Teslemetry integration."""

from __future__ import annotations

from typing import Any, cast

from tesla_fleet_api.const import Scope

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TeslemetryConfigEntry
from .entity import TeslemetryVehicleEntity
from .helpers import handle_vehicle_command
from .models import TeslemetryVehicleData

AVAILABLE = "available"
DOWNLOADING = "downloading"
INSTALLING = "installing"
WIFI_WAIT = "downloading_wifi_wait"
SCHEDULED = "scheduled"

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Teslemetry update platform from a config entry."""

    async_add_entities(
        TeslemetryUpdateEntity(vehicle, entry.runtime_data.scopes)
        for vehicle in entry.runtime_data.vehicles
    )


class TeslemetryUpdateEntity(TeslemetryVehicleEntity, UpdateEntity):
    """Teslemetry Updates entity."""

    def __init__(
        self,
        data: TeslemetryVehicleData,
        scopes: list[Scope],
    ) -> None:
        """Initialize the Update."""
        self.scoped = Scope.VEHICLE_CMDS in scopes
        super().__init__(
            data,
            "vehicle_state_software_update_status",
        )

    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""

        # Supported Features
        if self.scoped and self._value in (
            AVAILABLE,
            SCHEDULED,
        ):
            # Only allow install when an update has been fully downloaded
            self._attr_supported_features = (
                UpdateEntityFeature.PROGRESS | UpdateEntityFeature.INSTALL
            )
        else:
            self._attr_supported_features = UpdateEntityFeature.PROGRESS

        # Installed Version
        self._attr_installed_version = self.get("vehicle_state_car_version")
        if self._attr_installed_version is not None:
            # Remove build from version
            self._attr_installed_version = self._attr_installed_version.split(" ")[0]

        # Latest Version
        if self._value in (
            AVAILABLE,
            SCHEDULED,
            INSTALLING,
            DOWNLOADING,
            WIFI_WAIT,
        ):
            self._attr_latest_version = self.coordinator.data[
                "vehicle_state_software_update_version"
            ]
        else:
            self._attr_latest_version = self._attr_installed_version

        # In Progress
        if self._value in (
            SCHEDULED,
            INSTALLING,
        ):
            self._attr_in_progress = True
            if install_perc := self.get("vehicle_state_software_update_install_perc"):
                self._attr_update_percentage = cast(int, install_perc)
        else:
            self._attr_in_progress = False
            self._attr_update_percentage = None

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        self.raise_for_scope(Scope.ENERGY_CMDS)
        await self.wake_up_if_asleep()
        await handle_vehicle_command(self.api.schedule_software_update(offset_sec=60))
        self._attr_in_progress = True
        self._attr_update_percentage = None
        self.async_write_ha_state()
