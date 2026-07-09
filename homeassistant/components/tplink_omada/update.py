"""Support for TPLink Omada device firmware updates."""

from typing import Any, override

from tplink_omada_client.definitions import (
    OmadaHardwareUpdateInfo,
    OmadaSoftwareUpdateInfo,
)
from tplink_omada_client.devices import OmadaListDevice
from tplink_omada_client.exceptions import OmadaClientException, RequestFailed

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OmadaConfigEntry, config_entry_owns_controller_entities
from .coordinator import OmadaControllerCoordinator, OmadaFirmwareUpdateCoordinator
from .entity import OmadaControllerEntity, OmadaDeviceEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OmadaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up update entities."""
    controller = config_entry.runtime_data

    devices = controller.devices_coordinator.data

    coordinator = OmadaFirmwareUpdateCoordinator(
        hass, config_entry, controller.omada_client, controller.devices_coordinator
    )

    entities: list[UpdateEntity] = []
    if config_entry_owns_controller_entities(hass, config_entry):
        entities.append(OmadaControllerUpdate(controller.controller_coordinator))
    entities.extend(
        OmadaDeviceUpdate(coordinator, device) for device in devices.values()
    )

    async_add_entities(entities)
    await coordinator.async_request_refresh()


class OmadaControllerUpdate(OmadaControllerEntity, UpdateEntity):
    """Firmware/software update status for an Omada controller."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "firmware"

    def __init__(self, coordinator: OmadaControllerCoordinator) -> None:
        """Initialize the controller update entity."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.config_entry.runtime_data.controller_id}_firmware"
        )

    @property
    def _update_info(self) -> OmadaHardwareUpdateInfo | OmadaSoftwareUpdateInfo | None:
        """Return the best controller update data to expose."""
        updates = self.coordinator.data.updates
        if updates.hardware and updates.hardware.upgrade:
            return updates.hardware
        if updates.software and updates.software.upgrade:
            return updates.software
        return updates.hardware or updates.software

    @property
    def _hardware_update(self) -> OmadaHardwareUpdateInfo | None:
        """Return controller hardware firmware update data."""
        updates = self.coordinator.data.updates
        hardware = updates.hardware
        software = updates.software
        if hardware and hardware.upgrade:
            return hardware
        if software and software.upgrade:
            return None
        return hardware

    @property
    @override
    def supported_features(self) -> UpdateEntityFeature:
        """Flag supported features."""
        features = UpdateEntityFeature.RELEASE_NOTES
        if self._hardware_update:
            features |= UpdateEntityFeature.INSTALL
        return features

    @property
    @override
    def installed_version(self) -> str | None:
        """Return the installed controller version."""
        if self._update_info:
            return self._update_info.current_version
        return self.coordinator.data.info.controller_version

    @property
    @override
    def latest_version(self) -> str | None:
        """Return the latest controller version."""
        if self._update_info:
            return self._update_info.latest_version
        return self.coordinator.data.info.controller_version

    @override
    def release_notes(self) -> str | None:
        """Get the release notes for the latest controller update."""
        return self._update_info.release_notes if self._update_info else None

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install a controller hardware firmware update."""
        firmware = self._hardware_update
        if firmware is None:
            raise HomeAssistantError("No controller firmware update is available")

        try:
            await self.coordinator.omada_client.upgrade_controller_firmware(
                version or firmware.latest_version
            )
        except RequestFailed as ex:
            raise HomeAssistantError(
                "Controller firmware update request rejected"
            ) from ex
        except OmadaClientException as ex:
            raise HomeAssistantError(
                "Unable to send controller firmware update request."
                " Check the controller is online."
            ) from ex
        finally:
            await self.coordinator.async_request_refresh()


class OmadaDeviceUpdate(
    OmadaDeviceEntity[OmadaFirmwareUpdateCoordinator],
    UpdateEntity,
):
    """Firmware update status for Omada SDN devices."""

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.PROGRESS
        | UpdateEntityFeature.RELEASE_NOTES
    )
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_translation_key = "firmware"

    def __init__(
        self,
        coordinator: OmadaFirmwareUpdateCoordinator,
        device: OmadaListDevice,
    ) -> None:
        """Initialize the update entity."""
        super().__init__(coordinator, device)

        self._mac = device.mac
        self._omada_client = coordinator.omada_client

        self._attr_unique_id = f"{device.mac}_firmware"

    @override
    def release_notes(self) -> str | None:
        """Get the release notes for the latest update."""
        status = self.coordinator.data[self._mac]
        if status.firmware:
            return status.firmware.release_notes
        return None

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install a firmware update."""
        try:
            await self._omada_client.start_firmware_upgrade(
                self.coordinator.data[self._mac].device
            )
        except RequestFailed as ex:
            raise HomeAssistantError("Firmware update request rejected") from ex
        except OmadaClientException as ex:
            raise HomeAssistantError(
                "Unable to send Firmware update request."
                " Check the controller is online."
            ) from ex
        finally:
            await self.coordinator.async_request_refresh()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        status = self.coordinator.data[self._mac]

        if status.firmware and status.device.need_upgrade:
            self._attr_installed_version = status.firmware.current_version
            self._attr_latest_version = status.firmware.latest_version
        else:
            self._attr_installed_version = status.device.firmware_version
            self._attr_latest_version = status.device.firmware_version
        self._attr_in_progress = status.device.fw_download

        self.async_write_ha_state()
