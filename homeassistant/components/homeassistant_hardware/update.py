"""Home Assistant Hardware base firmware update entity."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
import logging
from typing import Any, cast

from ha_silabs_firmware_client import FirmwareManifest, FirmwareMetadata
from universal_silabs_flasher.firmware import parse_firmware_image
from universal_silabs_flasher.flasher import Flasher
from yarl import URL

from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.restore_state import ExtraStoredData
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import FirmwareUpdateCoordinator
from .helpers import async_register_firmware_info_callback
from .util import (
    ApplicationType,
    FirmwareInfo,
    guess_firmware_info,
    probe_silabs_firmware_info,
)

_LOGGER = logging.getLogger(__name__)

type FirmwareChangeCallbackType = Callable[
    [ApplicationType | None, ApplicationType | None], None
]


@dataclass(kw_only=True, frozen=True)
class FirmwareUpdateEntityDescription(UpdateEntityDescription):
    """Describes Home Assistant Hardware firmware update entity."""

    version_parser: Callable[[str], str]
    fw_type: str | None
    version_key: str | None
    expected_firmware_type: ApplicationType | None
    firmware_name: str | None


@dataclass
class FirmwareUpdateExtraStoredData(ExtraStoredData):
    """Extra stored data for Home Assistant Hardware firmware update entity."""

    firmware_manifest: FirmwareManifest | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the extra data."""
        return {
            "firmware_manifest": (
                self.firmware_manifest.as_dict()
                if self.firmware_manifest is not None
                else None
            )
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FirmwareUpdateExtraStoredData:
        """Initialize the extra data from a dict."""
        if data["firmware_manifest"] is None:
            return cls(firmware_manifest=None)

        return cls(
            FirmwareManifest.from_json(
                data["firmware_manifest"],
                # This data is not technically part of the manifest and is loaded externally
                url=URL(data["firmware_manifest"]["url"]),
                html_url=URL(data["firmware_manifest"]["html_url"]),
            )
        )


class BaseFirmwareUpdateEntity(
    CoordinatorEntity[FirmwareUpdateCoordinator], UpdateEntity
):
    """Base Home Assistant Hardware firmware update entity."""

    # Subclasses provide the mapping between firmware types and entity descriptions
    entity_description: FirmwareUpdateEntityDescription
    bootloader_reset_type: str | None = None

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )
    _attr_has_entity_name = True

    def __init__(
        self,
        device: str,
        config_entry: ConfigEntry,
        update_coordinator: FirmwareUpdateCoordinator,
        entity_description: FirmwareUpdateEntityDescription,
    ) -> None:
        """Initialize the Hardware firmware update entity."""
        super().__init__(update_coordinator)

        self.entity_description = entity_description
        self._current_device = device
        self._config_entry = config_entry
        self._current_firmware_info: FirmwareInfo | None = None
        self._firmware_type_change_callbacks: set[FirmwareChangeCallbackType] = set()

        self._latest_manifest: FirmwareManifest | None = None
        self._latest_firmware: FirmwareMetadata | None = None

    def add_firmware_type_changed_callback(
        self,
        change_callback: FirmwareChangeCallbackType,
    ) -> CALLBACK_TYPE:
        """Add a callback for when the firmware type changes."""
        self._firmware_type_change_callbacks.add(change_callback)

        @callback
        def remove_callback() -> None:
            self._firmware_type_change_callbacks.discard(change_callback)

        return remove_callback

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_register_firmware_info_callback(
                self.hass,
                self._current_device,
                self._firmware_info_callback,
            )
        )

        self.async_on_remove(
            self._config_entry.async_on_state_change(self._on_config_entry_change)
        )

        if (extra_data := await self.async_get_last_extra_data()) and (
            hardware_extra_data := FirmwareUpdateExtraStoredData.from_dict(
                extra_data.as_dict()
            )
        ):
            self._latest_manifest = hardware_extra_data.firmware_manifest

        self._update_attributes()

    @property
    def extra_restore_state_data(self) -> FirmwareUpdateExtraStoredData:
        """Return state data to be restored."""
        return FirmwareUpdateExtraStoredData(firmware_manifest=self._latest_manifest)

    @callback
    def _on_config_entry_change(self) -> None:
        """Handle config entry changes."""
        self._update_attributes()
        self.async_write_ha_state()

    @callback
    def _firmware_info_callback(self, firmware_info: FirmwareInfo) -> None:
        """Handle updated firmware info being pushed by an integration."""
        self._current_firmware_info = firmware_info

        # If the firmware type does not change, we can just update the attributes
        if (
            self._current_firmware_info.firmware_type
            == self.entity_description.expected_firmware_type
        ):
            self._update_attributes()
            self.async_write_ha_state()
            return

        # Otherwise, fire the firmware type change callbacks. They are expected to
        # replace the entity so there is no purpose in firing other callbacks.
        for change_callback in self._firmware_type_change_callbacks.copy():
            try:
                change_callback(
                    self.entity_description.expected_firmware_type,
                    self._current_firmware_info.firmware_type,
                )
            except Exception:  # noqa: BLE001
                _LOGGER.warning(
                    "Failed to call firmware type changed callback", exc_info=True
                )

    def _update_attributes(self) -> None:
        """Recompute the attributes of the entity."""
        self._attr_title = self.entity_description.firmware_name or "Unknown"

        if (
            self._current_firmware_info is None
            or self._current_firmware_info.firmware_version is None
        ):
            self._attr_installed_version = None
        else:
            self._attr_installed_version = self.entity_description.version_parser(
                self._current_firmware_info.firmware_version
            )

        self._latest_firmware = None
        self._attr_latest_version = None
        self._attr_release_summary = None
        self._attr_release_url = None

        if (
            self._latest_manifest is None
            or self.entity_description.fw_type is None
            or self.entity_description.version_key is None
        ):
            return

        try:
            self._latest_firmware = next(
                f
                for f in self._latest_manifest.firmwares
                if f.filename.startswith(self.entity_description.fw_type)
            )
        except StopIteration:
            pass
        else:
            version = cast(
                str, self._latest_firmware.metadata[self.entity_description.version_key]
            )
            self._attr_latest_version = self.entity_description.version_parser(version)
            self._attr_release_summary = self._latest_firmware.release_notes
            self._attr_release_url = str(self._latest_manifest.html_url)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._latest_manifest = self.coordinator.data
        self._update_attributes()
        self.async_write_ha_state()

    def _update_progress(self, offset: int, total_size: int) -> None:
        """Handle update progress."""

        # Firmware updates in ~30s so we still get responsive update progress even
        # without decimal places
        self._attr_update_percentage = round((offset * 100) / total_size)
        self.async_write_ha_state()

    @asynccontextmanager
    async def _temporarily_stop_hardware_owners(
        self, device: str
    ) -> AsyncIterator[None]:
        """Temporarily stop addons and integrations communicating with the device."""
        firmware_info = await guess_firmware_info(self.hass, device)
        _LOGGER.debug("Identified firmware info: %s", firmware_info)

        async with AsyncExitStack() as stack:
            for owner in firmware_info.owners:
                await stack.enter_async_context(owner.temporarily_stop(self.hass))

            yield

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        assert self._latest_firmware is not None
        assert self.entity_description.expected_firmware_type is not None

        # Start off by setting the progress bar to an indeterminate state
        self._attr_in_progress = True
        self._attr_update_percentage = None
        self.async_write_ha_state()

        fw_data = await self.coordinator.client.async_fetch_firmware(
            self._latest_firmware
        )
        fw_image = await self.hass.async_add_executor_job(parse_firmware_image, fw_data)

        device = self._current_device

        flasher = Flasher(
            device=device,
            probe_methods=(
                ApplicationType.GECKO_BOOTLOADER.as_flasher_application_type(),
                ApplicationType.EZSP.as_flasher_application_type(),
                ApplicationType.SPINEL.as_flasher_application_type(),
                ApplicationType.CPC.as_flasher_application_type(),
            ),
            bootloader_reset=self.bootloader_reset_type,
        )

        async with self._temporarily_stop_hardware_owners(device):
            try:
                try:
                    # Enter the bootloader with indeterminate progress
                    await flasher.enter_bootloader()

                    # Flash the firmware, with progress
                    await flasher.flash_firmware(
                        fw_image, progress_callback=self._update_progress
                    )
                except Exception as err:
                    raise HomeAssistantError("Failed to flash firmware") from err

                # Probe the running application type with indeterminate progress
                self._attr_update_percentage = None
                self.async_write_ha_state()

                firmware_info = await probe_silabs_firmware_info(
                    device,
                    probe_methods=(self.entity_description.expected_firmware_type,),
                )

                if firmware_info is None:
                    raise HomeAssistantError(
                        "Failed to probe the firmware after flashing"
                    )

                self._firmware_info_callback(firmware_info)
            finally:
                self._attr_in_progress = False
                self.async_write_ha_state()
