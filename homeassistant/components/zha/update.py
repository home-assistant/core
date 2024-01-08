"""Representation of ZHA updates."""
# pylint: skip-file
from __future__ import annotations

import asyncio
from datetime import datetime
import functools
from typing import TYPE_CHECKING, Any

import zigpy.exceptions
from zigpy.ota.image import BaseOTAImage
from zigpy.ota.manager import update_firmware
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
from homeassistant.helpers.start import async_at_start

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

    _attribute_name = "firmware_update"
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
        self._attr_installed_version: str = self.zha_device.sw_version or "unknown"
        self._latest_version_firmware: BaseOTAImage = None
        self._result = None

    @callback
    def device_ota_update_available(self, image: BaseOTAImage) -> None:
        """Handle update available."""
        self._latest_version_firmware = image
        self._attr_latest_version = image.header.file_version
        self.async_write_ha_state()

    @callback
    def _update_progress(self, current: int, total: int, progress: float) -> None:
        """Update install progress on event."""
        if not self._latest_version_firmware:
            return
        self._attr_in_progress = int(progress)
        self.async_write_ha_state()

    @callback
    def _reset_progress(self, write_state: bool = True) -> None:
        """Reset update install progress."""
        self._result = None
        self._attr_in_progress = False
        if write_state:
            self.async_write_ha_state()

    async def _async_update(self, _: HomeAssistant | datetime | None = None) -> None:
        """Update the entity."""
        await self._ota_cluster_handler.image_notify(
            payload_type=(
                self._ota_cluster_handler.cluster.ImageNotifyCommand.PayloadType.QueryJitter
            ),
            query_jitter=100,
        )

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        firmware = self._latest_version_firmware
        assert firmware
        self._reset_progress(False)
        self._attr_in_progress = True
        self.async_write_ha_state()

        try:
            self._result = await update_firmware(
                self.zha_device.device,
                self._latest_version_firmware,
                self._update_progress,
            )
        except (zigpy.exceptions.ZigbeeException, asyncio.TimeoutError) as ex:
            self._reset_progress()
            raise HomeAssistantError(ex) from ex

        # TODO: make this work for Zigpy
        assert self._result is not None

        # If the update was not successful, we should throw an error to let the user know
        if self._result != Status.SUCCESS:
            # TODO: make this work for Zigpy
            self._reset_progress()
            raise HomeAssistantError(
                "Update was not successful - result: {self._result}"
            )

        # If we get here, all files were installed successfully
        self._attr_installed_version = (
            self._attr_latest_version
        ) = firmware.header.file_version
        self._latest_version_firmware = None
        self._reset_progress()

    async def async_added_to_hass(self) -> None:
        """Call when entity is added."""
        await super().async_added_to_hass()
        # this is used to look for available firmware updates when HA starts
        self.async_on_remove(async_at_start(self.hass, self._async_update))
        self.zha_device.device.add_listener(self)

    async def async_will_remove_from_hass(self) -> None:
        """Call when entity will be removed."""
        await super().async_will_remove_from_hass()
        self._reset_progress(False)
