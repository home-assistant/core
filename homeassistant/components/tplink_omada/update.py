"""Support for TPLink Omada device firmware updates."""

from typing import Any, override

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

from . import OmadaConfigEntry
from .const import DOMAIN
from .coordinator import (
    OmadaControllerStatusCoordinator,
    OmadaControllerUpdateCoordinator,
    OmadaFirmwareUpdateCoordinator,
)
from .entity import OmadaControllerEntity, OmadaDeviceEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OmadaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up firmware updates."""
    controller = config_entry.runtime_data

    devices = controller.devices_coordinator.data

    coordinator = OmadaFirmwareUpdateCoordinator(
        hass, config_entry, controller.omada_client, controller.devices_coordinator
    )

    async_add_entities(
        [
            OmadaControllerUpdate(
                controller.controller_status_coordinator,
                controller.controller_update_coordinator,
            ),
            *(OmadaDeviceUpdate(coordinator, device) for device in devices.values()),
        ]
    )
    await coordinator.async_request_refresh()


class OmadaControllerUpdate(OmadaControllerEntity, UpdateEntity):
    """Firmware update status for the Omada Controller."""

    _attr_translation_key = "firmware"
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        status_coordinator: OmadaControllerStatusCoordinator,
        update_coordinator: OmadaControllerUpdateCoordinator,
    ) -> None:
        """Initialize the controller update entity."""
        super().__init__(status_coordinator)
        self._update_coordinator = update_coordinator
        self._omada_client = update_coordinator.omada_client
        self._attr_unique_id = f"{status_coordinator.data.mac}_firmware"

        self._update_attrs()

    @override
    async def async_added_to_hass(self) -> None:
        """Register for controller update coordinator changes."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._update_coordinator.async_add_listener(
                self._handle_update_coordinator_update
            )
        )

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._update_coordinator.last_update_success

    @callback
    def _handle_update_coordinator_update(self) -> None:
        """Handle updated controller firmware information."""
        self._update_attrs()
        self.async_write_ha_state()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated controller status data."""
        self._update_attrs()
        super()._handle_coordinator_update()

    def _update_attrs(self) -> None:
        """Update installed and latest controller versions."""
        update = self._update_coordinator.data
        installed_version = (
            update.current_version or self.coordinator.data.current_version
        )
        self._attr_installed_version = installed_version
        self._attr_latest_version = update.latest_version or installed_version
        self._attr_supported_features = UpdateEntityFeature.RELEASE_NOTES
        if update.hardware is not None:
            self._attr_supported_features |= UpdateEntityFeature.INSTALL

    @override
    def release_notes(self) -> str | None:
        """Return the release notes for the latest controller update."""
        return self._update_coordinator.data.release_notes

    @property
    @override
    def release_url(self) -> str | None:
        """Return the URL for the latest controller release notes."""
        return self._update_coordinator.data.release_url

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the controller update download URL."""
        update = self._update_coordinator.data.update
        if update is None or update.download_link is None:
            return None

        return {"download_url": update.download_link}

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install a controller firmware update."""
        update = self._update_coordinator.data

        if update.hardware is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="firmware_update_rejected",
            )

        target_version = version or update.latest_version
        if target_version is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="firmware_update_rejected",
            )

        try:
            await self._omada_client.install_controller_firmware(target_version)
        except OmadaClientException as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="firmware_update_failed",
            ) from ex
        finally:
            await self._update_coordinator.async_request_refresh()


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
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="firmware_update_rejected",
            ) from ex
        except OmadaClientException as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="firmware_update_failed",
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
