"""Update platform for Teslemetry integration."""

from __future__ import annotations

from typing import Any

from tesla_fleet_api.const import Scope
from tesla_fleet_api.teslemetry import Vehicle

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import TeslemetryConfigEntry
from .entity import (
    TeslemetryRootEntity,
    TeslemetryVehicleEntity,
    TeslemetryVehicleStreamEntity,
)
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
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Teslemetry update platform from a config entry."""

    async_add_entities(
        TeslemetryPollingUpdateEntity(vehicle, entry.runtime_data.scopes)
        if vehicle.api.pre2021 or vehicle.firmware < "2024.44.25"
        else TeslemetryStreamingUpdateEntity(vehicle, entry.runtime_data.scopes)
        for vehicle in entry.runtime_data.vehicles
    )


class TeslemetryUpdateEntity(TeslemetryRootEntity, UpdateEntity):
    """Teslemetry Updates entity."""

    api: Vehicle
    _attr_supported_features = UpdateEntityFeature.PROGRESS

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        self.raise_for_scope(Scope.VEHICLE_CMDS)

        await handle_vehicle_command(self.api.schedule_software_update(offset_sec=0))
        self._attr_in_progress = True
        self.async_write_ha_state()


class TeslemetryPollingUpdateEntity(TeslemetryVehicleEntity, TeslemetryUpdateEntity):
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
                self._attr_update_percentage = install_perc
        else:
            self._attr_in_progress = False
            self._attr_update_percentage = None


class TeslemetryStreamingUpdateEntity(
    TeslemetryVehicleStreamEntity, TeslemetryUpdateEntity, RestoreEntity
):
    """Teslemetry Updates entity."""

    _download_percentage: int = 0
    _install_percentage: int = 0

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

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        if (state := await self.async_get_last_state()) is not None:
            self._attr_in_progress = state.attributes.get("in_progress", False)
            self._install_percentage = state.attributes.get("install_percentage", False)
            self._attr_installed_version = state.attributes.get("installed_version")
            self._attr_latest_version = state.attributes.get("latest_version")
            self._attr_supported_features = UpdateEntityFeature(
                state.attributes.get(
                    "supported_features", self._attr_supported_features
                )
            )
            self.async_write_ha_state()

        self.async_on_remove(
            self.vehicle.stream_vehicle.listen_SoftwareUpdateDownloadPercentComplete(
                self._async_handle_software_update_download_percent_complete
            )
        )
        self.async_on_remove(
            self.vehicle.stream_vehicle.listen_SoftwareUpdateInstallationPercentComplete(
                self._async_handle_software_update_installation_percent_complete
            )
        )
        self.async_on_remove(
            self.vehicle.stream_vehicle.listen_SoftwareUpdateScheduledStartTime(
                self._async_handle_software_update_scheduled_start_time
            )
        )
        self.async_on_remove(
            self.vehicle.stream_vehicle.listen_SoftwareUpdateVersion(
                self._async_handle_software_update_version
            )
        )
        self.async_on_remove(
            self.vehicle.stream_vehicle.listen_Version(self._async_handle_version)
        )

    def _async_handle_software_update_download_percent_complete(
        self, value: float | None
    ):
        """Handle software update download percent complete."""

        self._download_percentage = round(value) if value is not None else 0
        if self.scoped and self._download_percentage == 100:
            self._attr_supported_features = (
                UpdateEntityFeature.PROGRESS | UpdateEntityFeature.INSTALL
            )
        else:
            self._attr_supported_features = UpdateEntityFeature.PROGRESS
        self._async_update_progress()
        self.async_write_ha_state()

    def _async_handle_software_update_installation_percent_complete(
        self, value: float | None
    ):
        """Handle software update installation percent complete."""

        self._install_percentage = round(value) if value is not None else 0
        self._async_update_progress()
        self.async_write_ha_state()

    def _async_handle_software_update_scheduled_start_time(self, value: str | None):
        """Handle software update scheduled start time."""

        self._attr_in_progress = value is not None
        self.async_write_ha_state()

    def _async_handle_software_update_version(self, value: str | None):
        """Handle software update version."""

        self._attr_latest_version = (
            value if value and value != " " else self._attr_installed_version
        )
        self.async_write_ha_state()

    def _async_handle_version(self, value: str | None):
        """Handle version."""

        if value is not None:
            self._attr_installed_version = value.split(" ")[0]
            self.async_write_ha_state()

    def _async_update_progress(self) -> None:
        """Update the progress of the update."""

        if self._download_percentage > 1 and self._download_percentage < 100:
            self._attr_in_progress = True
            self._attr_update_percentage = self._download_percentage
        elif self._install_percentage > 1:
            self._attr_in_progress = True
            self._attr_update_percentage = self._install_percentage
        else:
            self._attr_in_progress = False
            self._attr_update_percentage = None
