"""Support for TP-Link Omada updates."""

from typing import Any, override

from tplink_omada_client.definitions import (
    OmadaControllerInfo,
    OmadaControllerStatus,
    OmadaControllerType,
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OmadaConfigEntry
from .coordinator import (
    OmadaControllerUpdateCoordinator,
    OmadaFirmwareUpdateCoordinator,
)
from .entity import (
    OmadaControllerEntity,
    OmadaDeviceEntity,
    controller_device_identifier,
)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OmadaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Omada update entities."""
    controller = config_entry.runtime_data

    devices = controller.devices_coordinator.data

    device_coordinator = OmadaFirmwareUpdateCoordinator(
        hass, config_entry, controller.omada_client, controller.devices_coordinator
    )

    controller_coordinator = OmadaControllerUpdateCoordinator(
        hass, config_entry, controller.controller_client
    )
    await controller_coordinator.async_config_entry_first_refresh()

    controller_entities: list[UpdateEntity] = [
        OmadaControllerUpdate(
            controller_coordinator,
            config_entry,
            controller.controller_info,
            controller.controller_type,
            controller.controller_status,
            controller.controller_name,
        )
    ]

    async_add_entities(
        [
            *(
                OmadaDeviceUpdate(device_coordinator, device)
                for device in devices.values()
            ),
            *controller_entities,
        ]
    )
    await device_coordinator.async_request_refresh()


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


class OmadaControllerUpdate(
    OmadaControllerEntity[OmadaControllerUpdateCoordinator],
    UpdateEntity,
):
    """Firmware update status for an Omada controller."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "firmware"

    def __init__(
        self,
        coordinator: OmadaControllerUpdateCoordinator,
        config_entry: OmadaConfigEntry,
        controller_info: OmadaControllerInfo,
        controller_type: OmadaControllerType,
        controller_status: OmadaControllerStatus,
        controller_name: str,
    ) -> None:
        """Initialize the controller update entity."""
        super().__init__(
            coordinator,
            config_entry,
            controller_info,
            controller_type,
            controller_status,
            controller_name,
        )
        self._attr_unique_id = (
            f"{controller_device_identifier(config_entry)}_firmware"
        )
        self._controller_type = controller_type

    @property
    def update_info(
        self,
    ) -> OmadaHardwareUpdateInfo | OmadaSoftwareUpdateInfo | None:
        """Return update information for this controller type."""
        updates = self.coordinator.data
        if self._controller_type.is_soft_controller:
            return updates.software
        return updates.hardware

    @property
    def hardware_update(self) -> OmadaHardwareUpdateInfo | None:
        """Return installable controller hardware firmware information."""
        if self._controller_type.is_soft_controller:
            return None
        return self.coordinator.data.hardware

    @property
    @override
    def supported_features(self) -> UpdateEntityFeature:
        """Flag supported update features."""
        features = UpdateEntityFeature.RELEASE_NOTES
        if self.hardware_update is not None:
            features |= UpdateEntityFeature.INSTALL
        return features

    @property
    @override
    def installed_version(self) -> str:
        """Version currently installed."""
        if self.update_info is not None:
            return self.update_info.current_version
        return (
            self.coordinator.config_entry.runtime_data.controller_info.controller_version
        )

    @property
    @override
    def latest_version(self) -> str:
        """Latest version available."""
        if self.update_info is not None:
            return self.update_info.latest_version
        return (
            self.coordinator.config_entry.runtime_data.controller_info.controller_version
        )

    @override
    def release_notes(self) -> str | None:
        """Get the release notes for the latest controller update."""
        if self.update_info is None:
            return None
        return self.update_info.release_notes

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install a controller hardware firmware update."""
        firmware = self.hardware_update
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
                "Unable to update the Omada controller firmware."
                " Check the controller is online."
            ) from ex
        finally:
            await self.coordinator.async_request_refresh()
