"""Support for TPLink Omada device firmware updates."""

from dataclasses import dataclass
from typing import Any, override

from tplink_omada_client import OmadaControllerUpdateInfo
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
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import OmadaConfigEntry
from .controller import config_entry_owns_controller_entities
from .coordinator import (
    OmadaControllerInfoCoordinator,
    OmadaControllerUpdateCoordinator,
    OmadaFirmwareUpdateCoordinator,
)
from .entity import OmadaDeviceEntity, controller_device_info

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OmadaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switches."""
    controller = config_entry.runtime_data

    devices = controller.devices_coordinator.data

    if config_entry_owns_controller_entities(hass, config_entry):
        await controller.controller_update_coordinator.async_request_refresh()
        async_add_entities(
            [
                OmadaControllerUpdate(
                    controller.controller_update_coordinator,
                    controller.controller_info_coordinator,
                )
            ]
        )

    coordinator = OmadaFirmwareUpdateCoordinator(
        hass, config_entry, controller.omada_client, controller.devices_coordinator
    )

    async_add_entities(
        OmadaDeviceUpdate(coordinator, device) for device in devices.values()
    )
    await coordinator.async_request_refresh()


@dataclass(frozen=True, kw_only=True)
class ControllerUpdateDetails:
    """Controller update data normalized for the update entity."""

    current_version: str
    latest_version: str
    release_notes: str | None


def _controller_update_details(
    update_info: OmadaControllerUpdateInfo,
) -> ControllerUpdateDetails | None:
    """Return controller update data, preferring software over hardware updates."""
    for update in (update_info.software, update_info.hardware):
        if update:
            return ControllerUpdateDetails(
                current_version=update.current_version,
                latest_version=update.latest_version,
                release_notes=update.release_notes,
            )

    return None


class OmadaControllerUpdate(
    CoordinatorEntity[OmadaControllerUpdateCoordinator],
    UpdateEntity,
):
    """Update status for an Omada controller."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True
    _attr_supported_features = UpdateEntityFeature.RELEASE_NOTES
    _attr_translation_key = "firmware"

    def __init__(
        self,
        coordinator: OmadaControllerUpdateCoordinator,
        controller_info_coordinator: OmadaControllerInfoCoordinator,
    ) -> None:
        """Initialize the controller update entity."""
        super().__init__(coordinator)
        self._controller_info_coordinator = controller_info_coordinator
        self._attr_unique_id = (
            f"{controller_info_coordinator.data.omadac_id}_controller_firmware"
        )
        self._update_attrs()

    @property
    @override
    def device_info(self) -> dr.DeviceInfo:
        """Return device info for the Omada controller."""
        return controller_device_info(self._controller_info_coordinator.data)

    @override
    def release_notes(self) -> str | None:
        """Get the release notes for the latest update."""
        if self.coordinator.data and (
            update_details := _controller_update_details(self.coordinator.data)
        ):
            return update_details.release_notes
        return None

    @callback
    def _update_attrs(self) -> None:
        """Update entity attributes from the coordinator."""
        update_details = (
            _controller_update_details(self.coordinator.data)
            if self.coordinator.data
            else None
        )
        if update_details:
            self._attr_installed_version = update_details.current_version
            self._attr_latest_version = update_details.latest_version
        else:
            controller_version = (
                self._controller_info_coordinator.data.controller_version
            )
            self._attr_installed_version = controller_version
            self._attr_latest_version = controller_version

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attrs()
        self.async_write_ha_state()


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
