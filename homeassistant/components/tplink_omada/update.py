"""Support for TPLink Omada device firmware updates."""

from __future__ import annotations

from typing import Any

from tplink_omada_client.devices import OmadaListDevice
from tplink_omada_client.exceptions import OmadaClientException, RequestFailed

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OmadaConfigEntry
from .coordinator import OmadaFirmwareUpdateCoordinator
from .entity import OmadaDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OmadaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switches."""
    controller = config_entry.runtime_data

    devices = controller.devices_coordinator.data

    coordinator = OmadaFirmwareUpdateCoordinator(
        hass, config_entry, controller.omada_client, controller.devices_coordinator
    )

    async_add_entities(
        OmadaDeviceUpdate(coordinator, device) for device in devices.values()
    )
    await coordinator.async_request_refresh()


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

    def release_notes(self) -> str | None:
        """Get the release notes for the latest update."""
        status = self.coordinator.data[self._mac]
        if status.firmware:
            return status.firmware.release_notes
        return None

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
                "Unable to send Firmware update request. Check the controller is online."
            ) from ex
        finally:
            await self.coordinator.async_request_refresh()

    @callback
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
