"""Support for Daikin firmware update entities."""

from typing import Any, override

from daikin_onecta.models import ManagementPoint

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DaikinOnectaConfigEntry, OnectaDataUpdateCoordinator
from .device import DaikinOnectaDevice
from .entity import DaikinManagementPointEntity
from .entity_descriptions import UPDATE_DESCRIPTIONS

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DaikinOnectaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin update entities from a config entry."""
    coordinator: OnectaDataUpdateCoordinator = config_entry.runtime_data

    entities = [
        DaikinFirmwareUpdateEntity(
            coordinator,
            device,
            management_point,
        )
        for device in (coordinator.data or {}).values()
        for management_point in device.device.management_points
        if (firmware := management_point.firmware) is not None
        and firmware.has_installed_version
    ]

    async_add_entities(entities)


class DaikinFirmwareUpdateEntity(DaikinManagementPointEntity, UpdateEntity):
    """Represents the gateway firmware for a single Daikin device."""

    def __init__(
        self,
        coordinator: OnectaDataUpdateCoordinator,
        device: DaikinOnectaDevice,
        gateway_mp: ManagementPoint,
    ) -> None:
        """Initialise the update entity."""
        super().__init__(device, coordinator, gateway_mp.embedded_id)
        self._coordinator = coordinator
        self._pending_install: tuple[int, str | None] | None = None
        self.entity_description = UPDATE_DESCRIPTIONS["FirmwareUpdate"]

        self._attr_unique_id = f"{device.id}_{self._embedded_id}_firmware"

        # Populate initial state
        self._update_from_management_point(gateway_mp)

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Trigger a firmware update via the Daikin Onecta cloud API."""
        firmware_id = self._firmware_id
        if not self._is_update_supported or firmware_id is None:
            self._raise_service_validation_error("firmware_install_unavailable")

        await self._async_execute_command(
            lambda client: client.firmware(self._device.id, self._embedded_id).install(
                firmware_id
            ),
            "firmware_install_failed",
        )
        self._pending_install = (
            self.coordinator.cloud_update_sequence,
            self._attr_installed_version,
        )
        self._attr_supported_features |= UpdateEntityFeature.PROGRESS

        self.async_write_ha_state()

    @property
    @override
    def in_progress(self) -> bool | None:
        """Keep a requested install pending until the cloud reports its outcome."""
        return self._pending_install is not None or super().in_progress

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
            self._attr_in_progress = False
            self._is_update_supported = False
            self._attr_supported_features = UpdateEntityFeature(0)
            self._attr_extra_state_attributes = {}
            return
        self._attr_installed_version = firmware.installed_version
        self._is_update_supported = firmware.update_supported
        self._attr_latest_version = self._attr_installed_version
        self._attr_release_url = None
        self._attr_release_summary = None
        self._firmware_id = None
        self._attr_in_progress = False
        self._attr_supported_features = (
            UpdateEntityFeature.INSTALL
            if self._is_update_supported
            else UpdateEntityFeature(0)
        )
        self._attr_extra_state_attributes = {}

        if (firmware_update := firmware.offered_update) is not None:
            self._attr_latest_version = (
                firmware_update.version or self._attr_latest_version
            )
            self._attr_release_summary = firmware_update.description
            self._firmware_id = firmware.firmware_id
            if firmware_update_type := firmware_update.update_type:
                self._attr_extra_state_attributes["firmware_update_type"] = (
                    firmware_update_type
                )

        if firmware.has_update_status:
            self._attr_in_progress = firmware.in_progress
            self._attr_supported_features |= UpdateEntityFeature.PROGRESS

        if self._pending_install is not None:
            requested_sequence, installed_version = self._pending_install
            if self.coordinator.cloud_update_sequence > requested_sequence and (
                firmware.has_update_status
                or self._attr_installed_version != installed_version
            ):
                self._pending_install = None
            else:
                self._attr_supported_features |= UpdateEntityFeature.PROGRESS

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        mp = self._device.management_point(self._embedded_id)
        if mp is not None:
            self._update_from_management_point(mp)
        self.async_write_ha_state()

    @property
    @override
    def available(self) -> bool:
        """Return whether the source device is available."""
        return super().available and self._device.available
