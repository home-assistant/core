"""Home Assistant Hardware base firmware update entity."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
import logging
from typing import Any, cast

from universal_silabs_flasher.flasher import Flasher

from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.config_entries import (
    SIGNAL_CONFIG_ENTRY_CHANGED,
    ConfigEntry,
    ConfigEntryChange,
)
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import ExtraStoredData
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import FirmwareUpdateCoordinator
from .helpers import async_register_firmware_info_callback
from .models import FirmwareManifest, FirmwareMetadata
from .util import (
    ApplicationType,
    FirmwareInfo,
    guess_firmware_info,
    probe_silabs_firmware_info,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True, frozen=True)
class FirmwareUpdateEntityDescription(UpdateEntityDescription):
    """Describes Home Assistant Hardware firmware update entity."""

    version_parser: Callable[[str], str]
    fw_type: str
    version_key: str
    expected_firmware_type: ApplicationType
    firmware_name: str


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
            return cls()

        return cls(FirmwareManifest.from_json(data["firmware_manifest"]))


class BaseFirmwareUpdateEntity(
    CoordinatorEntity[FirmwareUpdateCoordinator], UpdateEntity
):
    """Base Home Assistant Hardware firmware update entity."""

    # Subclasses provide the mapping between firmware types and entity descriptions
    entity_description: FirmwareUpdateEntityDescription
    firmware_entity_descriptions: dict[ApplicationType, FirmwareUpdateEntityDescription]

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )
    _attr_has_entity_name = True

    def __init__(
        self,
        device: str,
        config_entry: ConfigEntry,
        update_coordinator: FirmwareUpdateCoordinator,
    ) -> None:
        """Initialize the Hardware firmware update entity."""
        super().__init__(update_coordinator)

        self._current_device = device
        self._config_entry = config_entry
        self._current_firmware_info: FirmwareInfo | None = None

        self._latest_manifest: FirmwareManifest | None = None
        self._latest_firmware: FirmwareMetadata | None = None
        self._maybe_recompute_state()

    def _firmware_info_callback(self, firmware_info: FirmwareInfo) -> None:
        self._current_firmware_info = firmware_info
        self._maybe_recompute_state()
        self.async_write_ha_state()

    @property
    def title(self) -> str:
        """Title of the software.

        This helps to differentiate between the device or entity name
        versus the title of the software installed.
        """
        return self.entity_description.firmware_name

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
            async_dispatcher_connect(
                self.hass,
                SIGNAL_CONFIG_ENTRY_CHANGED,
                self._on_config_entry_change,
            )
        )

        if (extra_data := await self.async_get_last_extra_data()) and (
            hardware_extra_data := FirmwareUpdateExtraStoredData.from_dict(
                extra_data.as_dict()
            )
        ):
            self._latest_manifest = hardware_extra_data.firmware_manifest
            self._maybe_recompute_state()
            self.async_write_ha_state()

    @property
    def extra_restore_state_data(self) -> FirmwareUpdateExtraStoredData:
        """Return Matter specific state data to be restored."""
        return FirmwareUpdateExtraStoredData(firmware_manifest=self._latest_manifest)

    @callback
    def _on_config_entry_change(
        self, change: ConfigEntryChange, entry: ConfigEntry
    ) -> None:
        """Handle config entry changes."""
        if entry != self._config_entry:
            return

        self._maybe_recompute_state()
        self.async_write_ha_state()

        # Update the firmware version in the device registry
        assert self.device_info is not None
        device_registry = dr.async_get(self.hass)
        device_registry.async_get_or_create(
            config_entry_id=self._config_entry.entry_id, **self.device_info
        )

    def _update_config_entry_after_install(self, firmware_info: FirmwareInfo) -> None:
        raise NotImplementedError

    def _maybe_recompute_state(self) -> None:
        """Recompute the state of the entity."""

        if self._current_firmware_info is None:
            firmware_type = None
        else:
            firmware_type = self._current_firmware_info.firmware_type

        if firmware_type not in self.firmware_entity_descriptions:
            _LOGGER.warning(
                "Unexpected firmware type %r, assuming Zigbee firmware instead",
                firmware_type,
            )
            firmware_type = ApplicationType.EZSP

        self.entity_description = self.firmware_entity_descriptions[firmware_type]
        if self._latest_manifest is None:
            return

        self._latest_firmware = next(
            f
            for f in self._latest_manifest.firmwares
            if f.filename.startswith(self.entity_description.fw_type)
        )

        version = cast(
            str, self._latest_firmware.metadata[self.entity_description.version_key]
        )
        self._attr_latest_version = self.entity_description.version_parser(version)
        self._attr_release_summary = self._latest_firmware.release_notes
        self._attr_release_url = str(self._latest_manifest.html_url)

        firmware_name = self.entity_description.firmware_name

        if (
            self._current_firmware_info is None
            or self._current_firmware_info.firmware_version is None
        ):
            sw_version = None
        else:
            firmware_version = self.entity_description.version_parser(
                self._current_firmware_info.firmware_version
            )
            sw_version = f"{firmware_name} {firmware_version}"

        if self.device_entry is not None:
            dr.async_get(self.hass).async_update_device(
                self.device_entry.id, sw_version=sw_version
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._latest_manifest = self.coordinator.data
        self._maybe_recompute_state()
        self.async_write_ha_state()

    @property
    def installed_version(self) -> str | None:
        """Version installed and in use."""
        if self._current_firmware_info is None:
            return None

        if (version := self._current_firmware_info.firmware_version) is None:
            return None

        return self.entity_description.version_parser(version)

    def _update_progress(self, offset: int, total_size: int) -> None:
        """Handle update progress."""
        self._attr_update_percentage = (offset * 100) / total_size
        self.async_write_ha_state()

    @asynccontextmanager
    async def _temporarily_stop_owning_software(
        self, device: str
    ) -> AsyncIterator[None]:
        """Temporarily stop owning addons and integrations."""

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

        # Start off by setting the progress bar to an indeterminate state
        self._attr_in_progress = True
        self._attr_update_percentage = None
        self.async_write_ha_state()

        async with self.coordinator.session.get(
            self._latest_firmware.url, raise_for_status=True
        ) as fw_rsp:
            fw_data = await fw_rsp.read()

        # At this point, we will have a valid firmware image that can be flasher
        fw_image = await self.hass.async_add_executor_job(
            self._latest_firmware.parse_firmware, fw_data
        )

        assert fw_image is not None
        device = self._current_device

        flasher = Flasher(
            device=device,
            probe_methods=(
                ApplicationType.GECKO_BOOTLOADER.as_flasher_application_type(),
                ApplicationType.EZSP.as_flasher_application_type(),
                ApplicationType.SPINEL.as_flasher_application_type(),
                ApplicationType.CPC.as_flasher_application_type(),
            ),
        )

        async with self._temporarily_stop_owning_software(device):
            try:
                # Enter the bootloader with indeterminate progress
                await flasher.enter_bootloader()

                # Flash the firmware, with progress
                await flasher.flash_firmware(
                    fw_image, progress_callback=self._update_progress
                )

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

                self._update_config_entry_after_install(firmware_info)
                self._firmware_info_callback(firmware_info)
            finally:
                self._attr_in_progress = False
                self.async_write_ha_state()
