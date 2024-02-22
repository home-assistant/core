"""Representation of ZHA updates."""
from __future__ import annotations

from dataclasses import dataclass
import functools
from typing import TYPE_CHECKING, Any

from zigpy.ota.image import BaseOTAImage
from zigpy.types import uint16_t
from zigpy.zcl.foundation import Status

from homeassistant.components.update import (
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
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
from homeassistant.helpers.restore_state import ExtraStoredData

from .core import discovery
from .core.const import CLUSTER_HANDLER_OTA, SIGNAL_ADD_ENTITIES, UNKNOWN
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


@dataclass
class ZHAFirmwareUpdateExtraStoredData(ExtraStoredData):
    """Extra stored data for ZHA firmware update entity."""

    image_type: uint16_t | None

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the extra data."""
        return {"image_type": self.image_type}


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
        self._attr_installed_version: str = self.determine_installed_version()
        self._image_type: uint16_t | None = None
        self._latest_version_firmware: BaseOTAImage | None = None
        self._result = None

    @callback
    def determine_installed_version(self) -> str:
        """Determine the currently installed firmware version."""
        currently_installed_version = self._ota_cluster_handler.current_file_version
        version_from_dr = self.zha_device.sw_version
        if currently_installed_version == UNKNOWN and version_from_dr:
            currently_installed_version = version_from_dr
        return currently_installed_version

    @property
    def extra_restore_state_data(self) -> ZHAFirmwareUpdateExtraStoredData:
        """Return ZHA firmware update specific state data to be restored."""
        return ZHAFirmwareUpdateExtraStoredData(self._image_type)

    @callback
    def device_ota_update_available(self, image: BaseOTAImage) -> None:
        """Handle ota update available signal from Zigpy."""
        self._latest_version_firmware = image
        self._attr_latest_version = f"0x{image.header.file_version:08x}"
        self._image_type = image.header.image_type
        self._attr_installed_version = self.determine_installed_version()
        self.async_write_ha_state()

    @callback
    def _update_progress(self, current: int, total: int, progress: float) -> None:
        """Update install progress on event."""
        assert self._latest_version_firmware
        self._attr_in_progress = int(progress)
        self.async_write_ha_state()

    @callback
    def _reset_progress(self, write_state: bool = True) -> None:
        """Reset update install progress."""
        self._result = None
        self._attr_in_progress = False
        if write_state:
            self.async_write_ha_state()

    async def async_update(self) -> None:
        """Handle the update entity service call to manually check for available firmware updates."""
        await super().async_update()
        # check for updates in the HA settings menu can invoke this so we need to check if the device
        # is mains powered so we don't get a ton of errors in the logs from sleepy devices.
        if self.zha_device.available and self.zha_device.is_mains_powered:
            await self._ota_cluster_handler.async_check_for_update()

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
            self._result = await self.zha_device.device.update_firmware(
                self._latest_version_firmware,
                self._update_progress,
            )
        except Exception as ex:
            self._reset_progress()
            raise HomeAssistantError(ex) from ex

        assert self._result is not None

        # If the update was not successful, we should throw an error to let the user know
        if self._result != Status.SUCCESS:
            # save result since reset_progress will clear it
            results = self._result
            self._reset_progress()
            raise HomeAssistantError(f"Update was not successful - result: {results}")

        # If we get here, all files were installed successfully
        self._attr_installed_version = (
            self._attr_latest_version
        ) = f"0x{firmware.header.file_version:08x}"
        self._latest_version_firmware = None
        self._reset_progress()

    async def async_added_to_hass(self) -> None:
        """Call when entity is added."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        # If we have a complete previous state, use that to set the installed version
        if (
            last_state
            and self._attr_installed_version == UNKNOWN
            and (installed_version := last_state.attributes.get(ATTR_INSTALLED_VERSION))
        ):
            self._attr_installed_version = installed_version
        # If we have a complete previous state, use that to set the latest version
        if (
            last_state
            and (latest_version := last_state.attributes.get(ATTR_LATEST_VERSION))
            is not None
            and latest_version != UNKNOWN
        ):
            self._attr_latest_version = latest_version
        # If we have no state or latest version to restore, or the latest version is
        # the same as the installed version, we can set the latest
        # version to installed so that the entity starts as off.
        elif (
            not last_state
            or not latest_version
            or latest_version == self._attr_installed_version
        ):
            self._attr_latest_version = self._attr_installed_version

        if self._attr_latest_version != self._attr_installed_version and (
            extra_data := await self.async_get_last_extra_data()
        ):
            self._image_type = extra_data.as_dict()["image_type"]
            if self._image_type:
                self._latest_version_firmware = (
                    await self.zha_device.device.application.ota.get_ota_image(
                        self.zha_device.manufacturer_code, self._image_type
                    )
                )
                # if we can't locate an image but we have a latest version that differs
                # we should set the latest version to the installed version to avoid
                # confusion and errors
                if not self._latest_version_firmware:
                    self._attr_latest_version = self._attr_installed_version

        self.zha_device.device.add_listener(self)

    async def async_will_remove_from_hass(self) -> None:
        """Call when entity will be removed."""
        await super().async_will_remove_from_hass()
        self._reset_progress(False)
