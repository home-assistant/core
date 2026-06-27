"""Support for TPLink Omada device firmware updates."""

from dataclasses import dataclass
from typing import Any, override

from tplink_omada_client import OmadaControllerInfo, OmadaControllerUpdateInfo
from tplink_omada_client.devices import OmadaListDevice
from tplink_omada_client.exceptions import OmadaClientException, RequestFailed

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import OmadaConfigEntry
from .config_flow import CONF_SITE
from .const import DOMAIN
from .coordinator import (
    OmadaControllerUpdateCoordinator,
    OmadaFirmwareUpdateCoordinator,
)
from .entity import OmadaDeviceEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OmadaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switches."""
    controller = config_entry.runtime_data

    devices = controller.devices_coordinator.data

    if _config_entry_owns_controller_entities(hass, config_entry):
        async_add_entities(
            [
                OmadaControllerUpdate(
                    controller.controller_update_coordinator,
                    controller.controller_info_coordinator.data,
                )
            ]
        )
        await controller.controller_update_coordinator.async_request_refresh()

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


def _config_entry_controller_unique_id(config_entry: ConfigEntry) -> str | None:
    """Return the controller-level unique ID for a site config entry."""
    unique_id = config_entry.unique_id
    site_id = config_entry.data.get(CONF_SITE)

    if unique_id is None or not isinstance(site_id, str):
        return unique_id

    site_suffix = f"_{site_id}"
    if unique_id.endswith(site_suffix):
        return unique_id[: -len(site_suffix)]

    return unique_id


def _config_entry_owns_controller_entities(
    hass: HomeAssistant, config_entry: OmadaConfigEntry
) -> bool:
    """Return if this site entry should add the controller-level entities."""
    controller_unique_id = _config_entry_controller_unique_id(config_entry)
    controller_entries = [
        entry
        for entry in hass.config_entries.async_entries(
            DOMAIN, include_ignore=False, include_disabled=False
        )
        if _config_entry_controller_unique_id(entry) == controller_unique_id
    ]

    return (
        config_entry.entry_id
        == min(
            controller_entries, key=lambda entry: (entry.created_at, entry.entry_id)
        ).entry_id
    )


def _controller_software_update(
    update_info: OmadaControllerUpdateInfo,
) -> ControllerUpdateDetails | None:
    """Return software controller update data when the API provides it."""
    raw_data = update_info.raw_data
    software_data = None
    for key in ("software", "controller", "controllerSoftware"):
        if key in raw_data:
            software_data = raw_data[key]
            break

    if software_data is None and "hardware" not in raw_data:
        software_data = raw_data

    if not software_data or not software_data.get("upgrade"):
        return None

    current_version = (
        software_data.get("currentVersion")
        or software_data.get("controllerVersion")
        or software_data.get("curVersion")
        or ""
    )
    latest_version = (
        software_data.get("latestVersion")
        or software_data.get("lastVersion")
        or software_data.get("newVersion")
        or software_data.get("version")
        or current_version
    )

    return ControllerUpdateDetails(
        current_version=current_version,
        latest_version=latest_version,
        release_notes=software_data.get("releaseLog")
        or software_data.get("fwReleaseLog")
        or software_data.get("releaseNotes"),
    )


def _controller_update_details(
    update_info: OmadaControllerUpdateInfo,
) -> ControllerUpdateDetails | None:
    """Return controller update data, preferring software over hardware updates."""
    if software_update := _controller_software_update(update_info):
        return software_update

    if hardware_update := update_info.hardware:
        if hardware_update.upgrade:
            return ControllerUpdateDetails(
                current_version=hardware_update.current_version,
                latest_version=hardware_update.latest_version,
                release_notes=hardware_update.release_notes,
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
    _attr_name = "Firmware"
    _attr_supported_features = UpdateEntityFeature.RELEASE_NOTES

    def __init__(
        self,
        coordinator: OmadaControllerUpdateCoordinator,
        controller_info: OmadaControllerInfo,
    ) -> None:
        """Initialize the controller update entity."""
        super().__init__(coordinator)
        self._controller_info = controller_info
        self._attr_unique_id = f"{controller_info.omadac_id}_controller_firmware"

    @property
    @override
    def device_info(self) -> dr.DeviceInfo:
        """Return device info for the Omada controller."""
        return dr.DeviceInfo(
            identifiers={(DOMAIN, self._controller_info.omadac_id)},
            manufacturer="TP-Link",
            model="Omada Controller",
            name="Omada Controller",
            sw_version=self._controller_info.controller_version,
        )

    @override
    def release_notes(self) -> str | None:
        """Get the release notes for the latest update."""
        if self.coordinator.data and (
            update_details := _controller_update_details(self.coordinator.data)
        ):
            return update_details.release_notes
        return None

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        update_details = (
            _controller_update_details(self.coordinator.data)
            if self.coordinator.data
            else None
        )
        if update_details:
            self._attr_installed_version = update_details.current_version
            self._attr_latest_version = update_details.latest_version
        else:
            self._attr_installed_version = self._controller_info.controller_version
            self._attr_latest_version = self._controller_info.controller_version

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
    _attr_name = "Firmware"

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
