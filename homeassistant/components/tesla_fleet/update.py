"""Update platform for Tesla Fleet integration."""

from __future__ import annotations

import time
from typing import Any

from tesla_fleet_api.const import Scope
from tesla_fleet_api.tesla.vehicle.fleet import VehicleFleet

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TeslaFleetConfigEntry
from .entity import TeslaFleetVehicleEntity
from .helpers import handle_vehicle_command
from .models import TeslaFleetVehicleData

AVAILABLE = "available"
DOWNLOADING = "downloading"
INSTALLING = "installing"
WIFI_WAIT = "downloading_wifi_wait"
SCHEDULED = "scheduled"

PARALLEL_UPDATES = 0

# Show scheduled update as installing if within this many seconds
SCHEDULED_THRESHOLD_SECONDS = 120


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeslaFleetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tesla Fleet update platform from a config entry."""

    async_add_entities(
        TeslaFleetUpdateEntity(vehicle, entry.runtime_data.scopes)
        for vehicle in entry.runtime_data.vehicles
    )


class TeslaFleetUpdateEntity(TeslaFleetVehicleEntity, UpdateEntity):
    """Tesla Fleet Update entity."""

    _attr_supported_features = UpdateEntityFeature.PROGRESS
    api: VehicleFleet

    def __init__(
        self,
        data: TeslaFleetVehicleData,
        scopes: list[Scope],
    ) -> None:
        """Initialize the Update."""
        self.scoped = Scope.VEHICLE_CMDS in scopes
        super().__init__(
            data,
            "vehicle_state_software_update_status",
        )

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        self.raise_for_read_only(Scope.VEHICLE_CMDS)

        await handle_vehicle_command(self.api.schedule_software_update(offset_sec=0))
        self._attr_in_progress = True
        self.async_write_ha_state()

    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""

        # Supported Features - only show install button if update is available
        # but not already scheduled
        if self.scoped and self._value == AVAILABLE:
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

        # Latest Version - hide update if scheduled far in the future
        if self._value in (AVAILABLE, INSTALLING, DOWNLOADING, WIFI_WAIT) or (
            self._value == SCHEDULED and self._is_scheduled_soon()
        ):
            self._attr_latest_version = self.coordinator.data[
                "vehicle_state_software_update_version"
            ]
        else:
            self._attr_latest_version = self._attr_installed_version

        # In Progress - only show as installing if actually installing or
        # scheduled to start within 2 minutes
        if self._value == INSTALLING:
            self._attr_in_progress = True
            if install_perc := self.get("vehicle_state_software_update_install_perc"):
                self._attr_update_percentage = install_perc
        elif self._value == SCHEDULED and self._is_scheduled_soon():
            self._attr_in_progress = True
            self._attr_update_percentage = None
        else:
            self._attr_in_progress = False
            self._attr_update_percentage = None

    def _is_scheduled_soon(self) -> bool:
        """Check if a scheduled update is within the threshold to start."""
        scheduled_time_ms = self.get("vehicle_state_software_update_scheduled_time_ms")
        if scheduled_time_ms is None:
            return False
        # Convert milliseconds to seconds and compare to current time
        scheduled_time_sec = scheduled_time_ms / 1000
        return scheduled_time_sec - time.time() < SCHEDULED_THRESHOLD_SECONDS
