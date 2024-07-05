"""Representation of ZHA updates."""

from __future__ import annotations

import functools
import logging
import math
from typing import TYPE_CHECKING, Any

from zigpy.ota import OtaImageWithMetadata
from zigpy.zcl.clusters.general import Ota
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
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .core import discovery
from .core.const import CLUSTER_HANDLER_OTA, SIGNAL_ADD_ENTITIES, SIGNAL_ATTR_UPDATED
from .core.helpers import get_zha_data, get_zha_gateway
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity

if TYPE_CHECKING:
    from zigpy.application import ControllerApplication

    from .core.cluster_handlers import ClusterHandler
    from .core.device import ZHADevice

_LOGGER = logging.getLogger(__name__)

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

    coordinator = ZHAFirmwareUpdateCoordinator(
        hass, get_zha_gateway(hass).application_controller
    )

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities,
            async_add_entities,
            entities_to_create,
            coordinator=coordinator,
        ),
    )
    config_entry.async_on_unload(unsub)


class ZHAFirmwareUpdateCoordinator(DataUpdateCoordinator[None]):  # pylint: disable=hass-enforce-coordinator-module
    """Firmware update coordinator that broadcasts updates network-wide."""

    def __init__(
        self, hass: HomeAssistant, controller_application: ControllerApplication
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="ZHA firmware update coordinator",
            update_method=self.async_update_data,
        )
        self.controller_application = controller_application

    async def async_update_data(self) -> None:
        """Fetch the latest firmware update data."""
        # Broadcast to all devices
        await self.controller_application.ota.broadcast_notify(jitter=100)


@CONFIG_DIAGNOSTIC_MATCH(cluster_handler_names=CLUSTER_HANDLER_OTA)
class ZHAFirmwareUpdateEntity(
    ZhaEntity, CoordinatorEntity[ZHAFirmwareUpdateCoordinator], UpdateEntity
):
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
        coordinator: ZHAFirmwareUpdateCoordinator,
        **kwargs: Any,
    ) -> None:
        """Initialize the ZHA update entity."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        CoordinatorEntity.__init__(self, coordinator)

        self._ota_cluster_handler: ClusterHandler = self.cluster_handlers[
            CLUSTER_HANDLER_OTA
        ]
        self._attr_installed_version: str | None = self._get_cluster_version()
        self._attr_latest_version = self._attr_installed_version
        self._latest_firmware: OtaImageWithMetadata | None = None

    def _get_cluster_version(self) -> str | None:
        """Synchronize current file version with the cluster."""

        if self._ota_cluster_handler.current_file_version is not None:
            return f"0x{self._ota_cluster_handler.current_file_version:08x}"

        return None

    @callback
    def attribute_updated(self, attrid: int, name: str, value: Any) -> None:
        """Handle attribute updates on the OTA cluster."""
        if attrid == Ota.AttributeDefs.current_file_version.id:
            self._attr_installed_version = f"0x{value:08x}"
            self.async_write_ha_state()

    @callback
    def device_ota_update_available(
        self, image: OtaImageWithMetadata, current_file_version: int
    ) -> None:
        """Handle ota update available signal from Zigpy."""
        self._latest_firmware = image
        self._attr_latest_version = f"0x{image.version:08x}"
        self._attr_installed_version = f"0x{current_file_version:08x}"

        if image.metadata.changelog:
            self._attr_release_summary = image.metadata.changelog

        self.async_write_ha_state()

    @callback
    def _update_progress(self, current: int, total: int, progress: float) -> None:
        """Update install progress on event."""
        # If we are not supposed to be updating, do nothing
        if self._attr_in_progress is False:
            return

        # Remap progress to 2-100 to avoid 0 and 1
        self._attr_in_progress = int(math.ceil(2 + 98 * progress / 100))
        self.async_write_ha_state()

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
                image=self._latest_firmware,
                progress_callback=self._update_progress,
            )
        except Exception as ex:
            raise HomeAssistantError(f"Update was not successful: {ex}") from ex

        # If we tried to install firmware that is no longer compatible with the device,
        # bail out
        if result == Status.NO_IMAGE_AVAILABLE:
            self._attr_latest_version = self._attr_installed_version
            self.async_write_ha_state()

        # If the update finished but was not successful, we should also throw an error
        if result != Status.SUCCESS:
            raise HomeAssistantError(f"Update was not successful: {result}")

        # Clear the state
        self._latest_firmware = None
        self._attr_in_progress = False
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Call when entity is added."""
        await super().async_added_to_hass()

        # OTA events are sent by the device
        self.zha_device.device.add_listener(self)
        self.async_accept_signal(
            self._ota_cluster_handler, SIGNAL_ATTR_UPDATED, self.attribute_updated
        )

    async def async_will_remove_from_hass(self) -> None:
        """Call when entity will be removed."""
        await super().async_will_remove_from_hass()
        self._attr_in_progress = False

    async def async_update(self) -> None:
        """Update the entity."""
        await CoordinatorEntity.async_update(self)
        await super().async_update()
