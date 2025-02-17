"""Representation of ZHA updates."""

from __future__ import annotations

import functools
import logging
from typing import Any

from zha.exceptions import ZHAException
from zigpy.application import ControllerApplication

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .entity import ZHAEntity
from .helpers import (
    SIGNAL_ADD_ENTITIES,
    EntityData,
    async_add_entities as zha_async_add_entities,
    get_zha_data,
    get_zha_gateway,
)

_LOGGER = logging.getLogger(__name__)

OTA_MESSAGE_BATTERY_POWERED = (
    "Battery powered devices can sometimes take multiple hours to update and you may"
    " need to wake the device for the update to begin."
)

ZHA_DOCS_NETWORK_RELIABILITY = "https://www.home-assistant.io/integrations/zha/#zigbee-interference-avoidance-and-network-rangecoverage-optimization"
OTA_MESSAGE_RELIABILITY = (
    "If you are having issues updating a specific device, make sure that you've"
    f" eliminated [common environmental issues]({ZHA_DOCS_NETWORK_RELIABILITY}) that"
    " could be affecting network reliability. OTA updates require a reliable network."
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation update from config entry."""
    zha_data = get_zha_data(hass)
    if zha_data.update_coordinator is None:
        zha_data.update_coordinator = ZHAFirmwareUpdateCoordinator(
            hass, get_zha_gateway(hass).application_controller
        )
    entities_to_create = zha_data.platforms[Platform.UPDATE]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            zha_async_add_entities,
            async_add_entities,
            ZHAFirmwareUpdateEntity,
            entities_to_create,
        ),
    )
    config_entry.async_on_unload(unsub)


class ZHAFirmwareUpdateCoordinator(DataUpdateCoordinator[None]):  # pylint: disable=hass-enforce-class-module
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


class ZHAFirmwareUpdateEntity(
    ZHAEntity, CoordinatorEntity[ZHAFirmwareUpdateCoordinator], UpdateEntity
):
    """Representation of a ZHA firmware update entity."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.PROGRESS
        | UpdateEntityFeature.SPECIFIC_VERSION
        | UpdateEntityFeature.RELEASE_NOTES
    )
    _attr_display_precision = 2  # 40 byte chunks with ~200KB files increments by 0.02%

    def __init__(self, entity_data: EntityData, **kwargs: Any) -> None:
        """Initialize the ZHA siren."""
        zha_data = get_zha_data(entity_data.device_proxy.gateway_proxy.hass)
        assert zha_data.update_coordinator is not None

        super().__init__(entity_data, coordinator=zha_data.update_coordinator, **kwargs)
        CoordinatorEntity.__init__(self, zha_data.update_coordinator)

    @property
    def installed_version(self) -> str | None:
        """Version installed and in use."""
        return self.entity_data.entity.installed_version

    @property
    def in_progress(self) -> bool | None:
        """Update installation progress.

        Should return a boolean (True if in progress, False if not).
        """
        return self.entity_data.entity.in_progress

    @property
    def update_percentage(self) -> int | float | None:
        """Update installation progress.

        Needs UpdateEntityFeature.PROGRESS flag to be set for it to be used.

        Can either return a number to indicate the progress from 0 to 100% or None.
        """
        return self.entity_data.entity.update_percentage

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        return self.entity_data.entity.latest_version

    @property
    def release_summary(self) -> str | None:
        """Summary of the release notes or changelog.

        This is not suitable for long changelogs, but merely suitable
        for a short excerpt update description of max 255 characters.
        """
        return self.entity_data.entity.release_summary

    async def async_release_notes(self) -> str | None:
        """Return full release notes.

        This is suitable for a long changelog that does not fit in the release_summary
        property. The returned string can contain markdown.
        """

        if self.entity_data.device_proxy.device.is_mains_powered:
            header = f"<ha-alert alert-type='info'>{OTA_MESSAGE_RELIABILITY}</ha-alert>"
        else:
            header = (
                "<ha-alert alert-type='info'>"
                f"{OTA_MESSAGE_BATTERY_POWERED} {OTA_MESSAGE_RELIABILITY}"
                "</ha-alert>"
            )

        return f"{header}\n\n{self.entity_data.entity.release_notes or ''}"

    @property
    def release_url(self) -> str | None:
        """URL to the full release notes of the latest version available."""
        return self.entity_data.entity.release_url

    # We explicitly convert ZHA exceptions to HA exceptions here so there is no need to
    # use the `@convert_zha_error_to_ha_error` decorator.
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        try:
            await self.entity_data.entity.async_install(version=version)
        except ZHAException as exc:
            raise HomeAssistantError(exc) from exc
        finally:
            self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the entity."""
        await CoordinatorEntity.async_update(self)
        await super().async_update()
