"""Support for TPLink Omada device toggle options."""
from __future__ import annotations

import logging
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

_LOGGER = logging.getLogger(__name__)


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

    entities: list = []
    for device in devices:
        entities.append(OmadaDeviceUpdate(coordinator, device))

    async_add_entities(entities)
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
    _firmware_update: OmadaFirmwareUpdate = None

    def __init__(
        self,
        coordinator: OmadaCoordinator[FirmwareUpdateStatus],
        device: OmadaListDevice,
    ) -> None:
        """Initialize the update entity."""
        super().__init__(coordinator, device)

        self._mac = device.mac
        self._device = device
        self._omada_client = coordinator.omada_client

        self._attr_unique_id = f"{device.mac}_firmware"
        self._attr_has_entity_name = True
        self._attr_name = "Firmware Update"
        self._refresh_state()

    def _refresh_state(self) -> None:
        if self._firmware_update and self._device.need_upgrade:
            self._attr_installed_version = self._firmware_update.current_version
            self._attr_latest_version = self._firmware_update.latest_version
        else:
            self._attr_installed_version = self._device.firmware_version
            self._attr_latest_version = self._device.firmware_version
        self._attr_in_progress = self._device.fw_download

        if self._attr_in_progress:
            # While firmware update is in progress, poll more frequently
            async_call_later(self.hass, 60, self._request_refresh)

    async def _request_refresh(self, _now: Any) -> None:
        await self.coordinator.async_request_refresh()

    def release_notes(self) -> str | None:
        """Get the release notes for the latest update."""
        if self._firmware_update:
            return str(self._firmware_update.release_notes)
        return ""

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install a firmware update."""
        if self._firmware_update and (
            version is None or self._firmware_update.latest_version == version
        ):
            await self._omada_client.start_firmware_upgrade(self._device)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Firmware upgrade is not available for %s", self._device.name)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        status = self.coordinator.data[self._mac]
        self._device = status.device
        self._firmware_update = status.firmware
        self._refresh_state()
        self.async_write_ha_state()
