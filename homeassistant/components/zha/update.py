"""Representation of ZHA updates."""
# pylint: skip-file
from __future__ import annotations

import asyncio
from datetime import datetime
import functools
from typing import TYPE_CHECKING, Any

from awesomeversion import AwesomeVersion
import zigpy.exceptions

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.start import async_at_start

from .core import discovery
from .core.const import CHANNEL_OTA, DATA_ZHA, SIGNAL_ADD_ENTITIES
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity

if TYPE_CHECKING:
    from .core.channels.base import ZigbeeChannel
    from .core.device import ZHADevice

STRICT_MATCH = functools.partial(ZHA_ENTITIES.strict_match, Platform.UPDATE)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation update from config entry."""
    entities_to_create = hass.data[DATA_ZHA][Platform.UPDATE]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities, async_add_entities, entities_to_create
        ),
    )
    config_entry.async_on_unload(unsub)


@STRICT_MATCH(channel_names=CHANNEL_OTA)
class ZHAFirmwareUpdateEntity(ZhaEntity, UpdateEntity):
    """Representation of a ZHA firmware update entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.PROGRESS
        | UpdateEntityFeature.SPECIFIC_VERSION
    )
    _attr_has_entity_name = True

    def __init__(
        self,
        unique_id: str,
        zha_device: ZHADevice,
        channels: list[ZigbeeChannel],
        **kwargs: Any,
    ) -> None:
        """Initialize the ZHA update entity."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._attr_name = "Firmware"
        self._ota_channel = self.cluster_channels[CHANNEL_OTA]
        self._attr_installed_version = self.zha_device.sw_version
        self._latest_version_firmware = None
        self._result = None

    @callback
    def _update_progress(self, details: dict[str, Any]) -> None:
        """Update install progress on event."""
        # TODO: need to determine Zigpy OTA progress status update event
        progress = details["firmware_update_progress"]
        if not self._latest_version_firmware:
            return
        self._attr_in_progress = int(progress.progress)
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

        # TODO do we want to be able to look into Zigpy for available updates?
        available_firmware_updates: list[Any] = []
        """
        try:
            # TODO: Zigpy won't need semaphore since it will be async / not remote
            async with self.semaphore:
                available_firmware_updates = (
                    await self.driver.controller.async_get_available_firmware_updates(
                        self.node, API_KEY_FIRMWARE_UPDATE_SERVICE
                    )
                )
        except FailedZWaveCommand as err:
            LOGGER.debug(
                "Failed to get firmware updates for node %s: %s",
                self.node.node_id,
                err,
            )
        else:
            """
        # If we have an available firmware update that is a higher version than
        # what's on the node, we should advertise it, otherwise the installed
        # version is the latest.
        if (
            available_firmware_updates
            and (
                latest_firmware := max(
                    available_firmware_updates,
                    key=lambda x: AwesomeVersion(x.version),
                )
            )
            # TODO: need to determine Zigpy OTA version comparison
            and AwesomeVersion(latest_firmware.version)
            # TODO: need to determine where to look for current version... channel maybe?
            > AwesomeVersion(self.zha_device.sw_version)
        ):
            self._latest_version_firmware = latest_firmware
            self._attr_latest_version = latest_firmware.version
            self.async_write_ha_state()
        elif self._attr_latest_version != self._attr_installed_version:
            self._attr_latest_version = self._attr_installed_version
            self.async_write_ha_state()

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
            # TODO fill in with Zigpy install OTA command _update_progress will be passed to Zigpy as callback
            # this call will block until the OTA is complete
            # self._result = await <some call into Zigpy>
            pass
        except (zigpy.exceptions.ZigbeeException, asyncio.TimeoutError) as ex:
            self._reset_progress()
            raise HomeAssistantError(ex) from ex

        # TODO: make this work for Zigpy
        assert self._result is not None

        # If the update was not successful, we should throw an error to let the user know
        if not self._result.success:
            # TODO: make this work for Zigpy
            error_msg = self._result.status.name.replace("_", " ").title()
            self._reset_progress()
            raise HomeAssistantError(error_msg)

        # If we get here, all files were installed successfully
        self._attr_installed_version = self._attr_latest_version = firmware.version
        self._latest_version_firmware = None
        self._reset_progress()

    async def async_added_to_hass(self) -> None:
        """Call when entity is added."""
        await super().async_added_to_hass()
        # this is used to look for available firmware updates when HA starts
        self.async_on_remove(async_at_start(self.hass, self._async_update))

    async def async_will_remove_from_hass(self) -> None:
        """Call when entity will be removed."""
        self._reset_progress(False)
