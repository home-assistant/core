"""Representation of ZHA updates."""
from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any

from zigpy.ota import OtaImageWithMetadata
from zigpy.zcl.foundation import Status

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .core import discovery
from .core.const import CLUSTER_HANDLER_OTA, SIGNAL_ADD_ENTITIES
from .core.helpers import get_zha_data
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity

if TYPE_CHECKING:
    from .core.cluster_handlers import ClusterHandler
    from .core.device import ZHADevice

CONFIG_DIAGNOSTIC_MATCH = functools.partial(
    ZHA_ENTITIES.config_diagnostic_match, Platform.UPDATE
)

# don't let homeassistant check for updates button hammer the zigbee network
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation update from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms[Platform.UPDATE]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities, async_add_entities, entities_to_create
        ),
    )
    config_entry.async_on_unload(unsub)


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_OTA)
class ZHAFirmwareUpdateEntity(ZhaEntity, UpdateEntity):
    """Representation of a ZHA firmware update entity."""

    _unique_id_suffix = "firmware_update"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.PROGRESS
        | UpdateEntityFeature.SPECIFIC_VERSION
    )

    def __init__(
        self,
        unique_id: str,
        zha_device: ZHADevice,
        channels: list[ClusterHandler],
        **kwargs: Any,
    ) -> None:
        """Initialize the ZHA update entity."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._ota_cluster_handler: ClusterHandler = self.cluster_handlers[
            CLUSTER_HANDLER_OTA
        ]
        self._attr_installed_version: str | None = self._get_cluster_version()
        self._latest_firmware: OtaImageWithMetadata | None = None

    def _get_cluster_version(self) -> str | None:
        """Synchronize current file version with the cluster."""

        device = (  # pylint: disable=protected-access
            self._ota_cluster_handler._endpoint.device
        )

        if self._ota_cluster_handler.current_file_version is not None:
            return f"0x{self._ota_cluster_handler.current_file_version:08x}"
        elif device.sw_version is not None:
            return device.sw_version

        return None

    @callback
    def device_ota_update_available(
        self, image: OtaImageWithMetadata, current_file_version: int
    ) -> None:
        """Handle ota update available signal from Zigpy."""
        self._latest_firmware = image
        self._attr_latest_version = f"0x{image.version:08x}"
        self._attr_installed_version = f"0x{current_file_version:08x}"
        self.async_write_ha_state()

    @callback
    def _update_progress(self, current: int, total: int, progress: float) -> None:
        """Update install progress on event."""
        self._attr_in_progress = int(progress)
        self.async_write_ha_state()

    @callback
    def _reset_progress(self, write_state: bool = True) -> None:
        """Reset update install progress."""
        self._attr_in_progress = False
        if write_state:
            self.async_write_ha_state()

    async def async_update(self) -> None:
        """Handle the update entity service call to manually check for available firmware updates."""
        await super().async_update()
        # "Check for updates" in the HA settings menu can invoke this so we need to
        # check if the device is mains powered so we don't get a ton of errors in the
        # logs from sleepy devices.
        if self.zha_device.available and self.zha_device.is_mains_powered:
            await self._ota_cluster_handler.async_check_for_update()

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        assert self._latest_firmware is not None

        # Set the progress to an indeterminate state
        self._attr_in_progress = True
        self.async_write_ha_state()

        try:
            result = await self.zha_device.device.update_firmware(
                firmware_image=self._latest_firmware,
                progress_callback=self._update_progress,
            )
        except Exception as ex:
            self._reset_progress()
            raise HomeAssistantError(f"Update was not successful: {ex}") from ex

        # If the update finished but was not successful, we should also throw an error
        if result != Status.SUCCESS:
            self._reset_progress()
            raise HomeAssistantError(f"Update was not successful: {result}")

        # Clear the state
        self._latest_firmware = None
        self._attr_installed_version = f"0x{self._latest_firmware.version:08x}"
        self._reset_progress()

    async def async_added_to_hass(self) -> None:
        """Call when entity is added."""
        await super().async_added_to_hass()
        self.zha_device.device.add_listener(self)

    async def async_will_remove_from_hass(self) -> None:
        """Call when entity will be removed."""
        await super().async_will_remove_from_hass()
        self._attr_in_progress = False
