"""Support for Daikin firmware update entities."""

import asyncio
from typing import Any, override

from daikin_onecta.models import ManagementPoint

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ENTITY_METADATA, entity_description_kwargs
from .coordinator import DaikinOnectaConfigEntry, OnectaDataUpdateCoordinator
from .device import DaikinOnectaDevice
from .entity import (
    DaikinManagementPointEntity,
    EntityIdChecker,
    add_entities_on_coordinator_update,
    iter_management_points,
)
from .utils import management_point_unique_id

PARALLEL_UPDATES = 1

UPDATE_DESCRIPTIONS = {
    metadata.key: UpdateEntityDescription(
        key=metadata.key,
        device_class=metadata.device_class,
        **entity_description_kwargs(metadata),
    )
    for metadata in ENTITY_METADATA
    if isinstance(metadata.device_class, UpdateDeviceClass)
}

_INSTALL_CONFIRMATION_POLLS = 3


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DaikinOnectaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin update entities from a config entry."""
    coordinator: OnectaDataUpdateCoordinator = config_entry.runtime_data
    add_entities_on_coordinator_update(
        hass,
        config_entry,
        coordinator,
        async_add_entities,
        lambda is_known: _create_firmware_entities(coordinator, is_known),
    )


def _create_firmware_entities(
    coordinator: OnectaDataUpdateCoordinator,
    is_known: EntityIdChecker,
) -> list[DaikinFirmwareUpdateEntity]:
    """Create firmware update entities from the current cloud model."""
    return [
        DaikinFirmwareUpdateEntity(
            coordinator,
            device,
            management_point,
        )
        for device, management_point in iter_management_points(coordinator)
        if management_point.firmware is not None
        and (
            (
                management_point.is_firmware_update_supported is not None
                and management_point.is_firmware_update_supported.value is True
            )
            or management_point.firmware_update is not None
            or management_point.firmware_update_status is not None
        )
        and not is_known(
            Platform.UPDATE,
            management_point_unique_id(
                device.id, management_point.embedded_id, "firmware"
            ),
        )
    ]


class DaikinFirmwareUpdateEntity(DaikinManagementPointEntity, UpdateEntity):
    """Represents the gateway firmware for a single Daikin device."""

    entity_description = UPDATE_DESCRIPTIONS["FirmwareUpdate"]

    def __init__(
        self,
        coordinator: OnectaDataUpdateCoordinator,
        device: DaikinOnectaDevice,
        gateway_mp: ManagementPoint,
    ) -> None:
        """Initialise the update entity."""
        super().__init__(device, coordinator, gateway_mp.embedded_id)
        self._pending_install: tuple[int, str | None, int] | None = None

        self._attr_unique_id = management_point_unique_id(
            device.id, self._embedded_id, "firmware"
        )

        self._update_from_management_point(gateway_mp)

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Trigger a firmware update via the Daikin Onecta cloud API."""
        firmware_id = self._firmware_id
        if not self._is_update_supported or firmware_id is None:
            self._raise_service_validation_error("firmware_install_unavailable")

        requested_sequence = self.coordinator.cloud_update_sequence
        self._set_pending_install(requested_sequence)
        self._attr_supported_features |= UpdateEntityFeature.PROGRESS
        self.async_write_ha_state()
        try:
            await self._async_execute_command(
                lambda client: client.firmware(
                    self._device_id, self._embedded_id
                ).install(firmware_id),
                "firmware_install_failed",
            )
        except HomeAssistantError, asyncio.CancelledError:
            self._pending_install = None
            management_point = self._management_point
            if management_point is not None:
                self._update_from_management_point(management_point)
            else:
                self._attr_supported_features &= ~UpdateEntityFeature.PROGRESS
            self.async_write_ha_state()
            raise
        requested_sequence = self.coordinator.cloud_update_sequence
        self._set_pending_install(requested_sequence)
        self.coordinator.schedule_post_write_refresh()

    def _set_pending_install(self, requested_sequence: int) -> None:
        """Keep the requested update pending until cloud state confirms it."""
        installed_version = (
            self._pending_install[1]
            if self._pending_install is not None
            else self._attr_installed_version
        )
        self._pending_install = (
            requested_sequence,
            installed_version,
            requested_sequence + _INSTALL_CONFIRMATION_POLLS,
        )

    @property
    @override
    def in_progress(self) -> bool | None:
        """Keep a requested install pending until the cloud reports its outcome."""
        if self._pending_install is not None:
            return True
        management_point = self._management_point
        firmware = management_point.firmware if management_point is not None else None
        if firmware is not None and firmware.has_update_status:
            return firmware.in_progress
        return False

    def _update_from_management_point(self, management_point: ManagementPoint) -> None:
        """Pull the latest values out of a typed management point."""
        firmware = management_point.firmware
        if firmware is None:
            self._pending_install = None
            self._attr_installed_version = None
            self._attr_latest_version = None
            self._attr_release_url = None
            self._attr_release_summary = None
            self._firmware_id = None
            self._is_update_supported = False
            self._attr_supported_features = UpdateEntityFeature(0)
            self._attr_extra_state_attributes = {}
            return
        self._attr_installed_version = firmware.installed_version
        self._is_update_supported = firmware.update_supported
        self._attr_latest_version = self._attr_installed_version
        self._attr_release_url = None
        self._attr_release_summary = None
        offered_update = firmware.offered_update
        self._firmware_id = (
            offered_update.firmware_id if offered_update is not None else None
        )
        self._attr_supported_features = (
            UpdateEntityFeature.INSTALL
            if self._is_update_supported and self._firmware_id is not None
            else UpdateEntityFeature(0)
        )
        self._attr_extra_state_attributes = {}

        if offered_update is not None:
            self._attr_latest_version = (
                offered_update.version or self._attr_latest_version
            )
            self._attr_release_summary = offered_update.description
            if firmware_update_type := offered_update.update_type:
                self._attr_extra_state_attributes["firmware_update_type"] = (
                    firmware_update_type
                )

        if firmware.has_update_status:
            self._attr_supported_features |= UpdateEntityFeature.PROGRESS

        if self._pending_install is not None:
            requested_sequence, installed_version, expiry_sequence = (
                self._pending_install
            )
            if self.coordinator.cloud_update_sequence > requested_sequence and (
                firmware.in_progress
                or (
                    installed_version is not None
                    and self._attr_installed_version is not None
                    and self._attr_installed_version != installed_version
                )
                or self.coordinator.cloud_update_sequence >= expiry_sequence
            ):
                self._pending_install = None
            else:
                self._attr_supported_features |= UpdateEntityFeature.PROGRESS

    @override
    def update_state(self) -> None:
        """Refresh firmware update state from the current management point."""
        mp = self._management_point
        if mp is not None:
            self._update_from_management_point(mp)

    @property
    @override
    def available(self) -> bool:
        """Return whether the source device is available."""
        if not super().available:
            return False

        management_point = self._management_point
        if management_point is None:
            return False
        # Daikin can omit the installed version while still reporting update
        # status or an available firmware offer. Keep the update entity usable.
        return management_point.firmware is not None
