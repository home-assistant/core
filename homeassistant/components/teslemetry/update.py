"""Update platform for Teslemetry integration."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, override

from tesla_fleet_api import firmware_at_least
from tesla_fleet_api.const import Scope
from tesla_fleet_api.teslemetry import Vehicle

from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityFeature,
    UpdateEntityStateAttribute,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.util import dt as dt_util

from . import TeslemetryConfigEntry
from .entity import (
    TeslemetryRootEntity,
    TeslemetryVehiclePollingEntity,
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

ATTR_SCHEDULED_AT = "scheduled_at"
ATTR_DOWNLOAD_PERCENTAGE = "download_percentage"
ATTR_INSTALL_PERCENTAGE = "install_percentage"

# A scheduled install normally begins within hours. A schedule this old was
# never followed by the clearing push it should have received, so treat it
# as abandoned rather than keep the entity latched on "installing" forever.
SCHEDULED_STALE_AFTER = timedelta(days=2)


@dataclass
class TeslemetryUpdateExtraStoredData(ExtraStoredData):
    """Extra stored data for the streaming update entity."""

    scheduled_at: datetime | None = None
    download_percentage: int = 0
    install_percentage: int = 0

    @override
    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the extra data."""
        return {
            ATTR_SCHEDULED_AT: self.scheduled_at.isoformat()
            if self.scheduled_at is not None
            else None,
            ATTR_DOWNLOAD_PERCENTAGE: self.download_percentage,
            ATTR_INSTALL_PERCENTAGE: self.install_percentage,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TeslemetryUpdateExtraStoredData:
        """Initialize the extra data from a dict."""
        scheduled_at = data[ATTR_SCHEDULED_AT]
        return cls(
            dt_util.parse_datetime(scheduled_at) if scheduled_at is not None else None,
            data.get(ATTR_DOWNLOAD_PERCENTAGE, 0),
            data.get(ATTR_INSTALL_PERCENTAGE, 0),
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Teslemetry update platform from a config entry."""

    async_add_entities(
        TeslemetryVehiclePollingUpdateEntity(vehicle, entry.runtime_data.scopes)
        if vehicle.poll or not firmware_at_least(vehicle.firmware, "2024.44.25")
        else TeslemetryStreamingUpdateEntity(vehicle, entry.runtime_data.scopes)
        for vehicle in entry.runtime_data.vehicles
    )


class TeslemetryUpdateEntity(TeslemetryRootEntity, UpdateEntity):
    """Teslemetry Updates entity."""

    api: Vehicle
    _attr_supported_features = UpdateEntityFeature.PROGRESS

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        self.raise_for_scope(Scope.VEHICLE_CMDS)

        await handle_vehicle_command(self.api.schedule_software_update(offset_sec=0))
        self._attr_in_progress = True
        self.async_write_ha_state()


class TeslemetryVehiclePollingUpdateEntity(
    TeslemetryVehiclePollingEntity, TeslemetryUpdateEntity
):
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

    @override
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
    _scheduled: bool = False
    _scheduled_at: datetime | None = None
    _cancel_scheduled_expiry: CALLBACK_TYPE | None = None

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

    @override
    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        if (extra_data := await self.async_get_last_extra_data()) is not None:
            extra = TeslemetryUpdateExtraStoredData.from_dict(extra_data.as_dict())
            self._scheduled_at = extra.scheduled_at
            self._download_percentage = extra.download_percentage
            self._install_percentage = extra.install_percentage
        if (state := await self.async_get_last_state()) is not None:
            self._attr_installed_version = state.attributes.get(
                UpdateEntityStateAttribute.INSTALLED_VERSION
            )
            self._attr_latest_version = state.attributes.get(
                UpdateEntityStateAttribute.LATEST_VERSION
            )
            self._attr_supported_features = UpdateEntityFeature(
                state.attributes.get(
                    "supported_features", self._attr_supported_features
                )
            )
            # A restored in-progress flag with installed == latest is a missed
            # completion; restoring it would re-strand the entity every restart.
            if not self._up_to_date:
                self._attr_in_progress = state.attributes.get(
                    UpdateEntityStateAttribute.IN_PROGRESS, False
                )
                self._attr_update_percentage = state.attributes.get(
                    UpdateEntityStateAttribute.UPDATE_PERCENTAGE
                )
                self._scheduled = self._attr_in_progress
                # A restored in-progress flag caused only by the scheduled latch
                # (no real download/install percentage) is unverifiable once its
                # schedule has gone stale; a genuine one re-arms its own expiry.
                if self._scheduled and self._attr_update_percentage is None:
                    if self._scheduled_stale:
                        self._attr_in_progress = False
                        self._scheduled = False
                    else:
                        self._async_arm_scheduled_expiry()
            self.async_write_ha_state()

        self.async_on_remove(self._async_cancel_scheduled_expiry)
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
    ) -> None:
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
    ) -> None:
        """Handle software update installation percent complete."""

        self._install_percentage = round(value) if value is not None else 0
        self._async_update_progress()
        self.async_write_ha_state()

    def _async_handle_software_update_scheduled_start_time(
        self, value: int | None
    ) -> None:
        """Handle software update scheduled start time."""

        self._scheduled = value is not None
        self._scheduled_at = dt_util.utcnow() if value is not None else None
        self._async_arm_scheduled_expiry()
        self._async_update_progress()
        self.async_write_ha_state()

    @callback
    def _async_cancel_scheduled_expiry(self) -> None:
        """Cancel any pending scheduled-expiry timer."""
        if self._cancel_scheduled_expiry is not None:
            self._cancel_scheduled_expiry()
            self._cancel_scheduled_expiry = None

    @callback
    def _async_arm_scheduled_expiry(self) -> None:
        """(Re)start the timer that clears the scheduled flag once it is stale."""
        self._async_cancel_scheduled_expiry()
        if self._scheduled_at is not None and not self._scheduled_stale:
            self._cancel_scheduled_expiry = async_track_point_in_utc_time(
                self.hass,
                self._async_handle_scheduled_expiry,
                self._scheduled_at + SCHEDULED_STALE_AFTER,
            )

    @callback
    def _async_handle_scheduled_expiry(self, _now: datetime) -> None:
        """Clear an expired scheduled flag and refresh progress."""
        self._cancel_scheduled_expiry = None
        self._scheduled = False
        self._scheduled_at = None
        self._async_update_progress()
        self.async_write_ha_state()

    def _async_handle_software_update_version(self, value: str | None) -> None:
        """Handle software update version."""

        self._attr_latest_version = (
            value if value and value != " " else self._attr_installed_version
        )
        self.async_write_ha_state()

    def _async_handle_version(self, value: str | None) -> None:
        """Handle version."""

        if value is not None:
            self._attr_installed_version = value.split(" ")[0]
            # A new installed version can be the only signal that an offline
            # install finished, so re-evaluate any lingering scheduled flag.
            self._async_update_progress()
            self.async_write_ha_state()

    @property
    def _up_to_date(self) -> bool:
        """Return True when the installed version matches the known latest version."""
        return (
            self._attr_installed_version is not None
            and self._attr_installed_version == self._attr_latest_version
        )

    @property
    def _scheduled_stale(self) -> bool:
        """Return True when the scheduled flag has outlived its staleness bound."""
        return (
            self._scheduled_at is None
            or dt_util.utcnow() - self._scheduled_at > SCHEDULED_STALE_AFTER
        )

    @property
    @override
    def extra_restore_state_data(self) -> TeslemetryUpdateExtraStoredData:
        """Return entity specific state data to be restored."""
        return TeslemetryUpdateExtraStoredData(
            self._scheduled_at, self._download_percentage, self._install_percentage
        )

    def _async_update_progress(self) -> None:
        """Update the progress of the update."""

        if 0 < self._download_percentage < 100:
            self._attr_in_progress = True
            self._attr_update_percentage = self._download_percentage
        elif 10 < self._install_percentage < 100:
            self._attr_in_progress = True
            self._attr_update_percentage = self._install_percentage
        elif self._scheduled and not self._up_to_date and not self._scheduled_stale:
            self._attr_in_progress = True
            self._attr_update_percentage = None
        else:
            self._attr_in_progress = False
            self._attr_update_percentage = None
