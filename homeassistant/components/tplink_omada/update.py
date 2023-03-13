"""Support for TPLink Omada device firmware updates."""
from __future__ import annotations

from typing import Any, NamedTuple

from tplink_omada_client.devices import OmadaFirmwareUpdate, OmadaListDevice
from tplink_omada_client.omadasiteclient import OmadaSiteClient

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN
from .controller import OmadaSiteController
from .coordinator import OmadaCoordinator
from .entity import OmadaDeviceEntity


class FirmwareUpdateStatus(NamedTuple):
    """Firmware update information for Omada SDN devices."""

    device: OmadaListDevice
    firmware: OmadaFirmwareUpdate | None


async def _get_firmware_updates(client: OmadaSiteClient) -> list[FirmwareUpdateStatus]:
    devices = await client.get_devices()
    return [
        FirmwareUpdateStatus(
            device=d,
            firmware=None
            if not d.need_upgrade
            else await client.get_firmware_details(d),
        )
        for d in devices
    ]


async def _poll_firmware_updates(
    client: OmadaSiteClient,
) -> dict[str, FirmwareUpdateStatus]:
    """Poll the state of Omada Devices firmware update availability."""
    return {d.device.mac: d for d in await _get_firmware_updates(client)}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""
    controller: OmadaSiteController = hass.data[DOMAIN][config_entry.entry_id]
    omada_client = controller.omada_client

    devices = await omada_client.get_devices()

    coordinator = OmadaCoordinator[FirmwareUpdateStatus](
        hass,
        omada_client,
        "Firmware Updates",
        _poll_firmware_updates,
        poll_delay=6 * 60 * 60,
    )

    async_add_entities(OmadaDeviceUpdate(coordinator, device) for device in devices)
    await coordinator.async_request_refresh()


class OmadaDeviceUpdate(
    OmadaDeviceEntity[FirmwareUpdateStatus],
    UpdateEntity,
):
    """Firmware update status for Omada SDN devices."""

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.PROGRESS
        | UpdateEntityFeature.RELEASE_NOTES
    )
    _attr_has_entity_name = True
    _attr_name = "Firmware update"

    def __init__(
        self,
        coordinator: OmadaCoordinator[FirmwareUpdateStatus],
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
        await self._omada_client.start_firmware_upgrade(
            self.coordinator.data[self._mac].device
        )
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

        if self._attr_in_progress:
            # While firmware update is in progress, poll more frequently
            async def do_refresh(*_: Any) -> None:
                await self.coordinator.async_request_refresh()

            async_call_later(self.hass, 60, do_refresh)

        self.async_write_ha_state()
