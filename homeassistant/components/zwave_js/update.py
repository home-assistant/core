"""Representation of Z-Wave updates."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from awesomeversion import AwesomeVersion
from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import NodeStatus
from zwave_js_server.exceptions import BaseZwaveJSServerError, FailedZWaveCommand
from zwave_js_server.model.driver import Driver
from zwave_js_server.model.node import Node as ZwaveNode
from zwave_js_server.model.node.firmware import (
    NodeFirmwareUpdateInfo,
    NodeFirmwareUpdateProgress,
    NodeFirmwareUpdateResult,
)

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.start import async_at_start

from .const import API_KEY_FIRMWARE_UPDATE_SERVICE, DATA_CLIENT, DOMAIN, LOGGER
from .helpers import get_device_info, get_valueless_base_unique_id

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Z-Wave button from config entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    semaphore = asyncio.Semaphore(3)

    @callback
    def async_add_firmware_update_entity(node: ZwaveNode) -> None:
        """Add firmware update entity."""
        driver = client.driver
        assert driver is not None  # Driver is ready before platforms are loaded.
        async_add_entities([ZWaveNodeFirmwareUpdate(driver, node, semaphore)])

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_firmware_update_entity",
            async_add_firmware_update_entity,
        )
    )


class ZWaveNodeFirmwareUpdate(UpdateEntity):
    """Representation of a firmware update entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.RELEASE_NOTES
        | UpdateEntityFeature.PROGRESS
    )
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self, driver: Driver, node: ZwaveNode, semaphore: asyncio.Semaphore
    ) -> None:
        """Initialize a Z-Wave device firmware update entity."""
        self.driver = driver
        self.node = node
        self.semaphore = semaphore
        self._latest_version_firmware: NodeFirmwareUpdateInfo | None = None
        self._status_unsub: Callable[[], None] | None = None
        self._poll_unsub: Callable[[], None] | None = None
        self._progress_unsub: Callable[[], None] | None = None
        self._finished_unsub: Callable[[], None] | None = None
        self._finished_event = asyncio.Event()
        self._result: NodeFirmwareUpdateResult | None = None

        # Entity class attributes
        self._attr_name = "Firmware"
        self._base_unique_id = get_valueless_base_unique_id(driver, node)
        self._attr_unique_id = f"{self._base_unique_id}.firmware_update"
        self._attr_installed_version = node.firmware_version
        # device may not be precreated in main handler yet
        self._attr_device_info = get_device_info(driver, node)

    @callback
    def _update_on_status_change(self, _: dict[str, Any]) -> None:
        """Update the entity when node is awake."""
        self._status_unsub = None
        self.hass.async_create_task(self._async_update())

    @callback
    def _update_progress(self, event: dict[str, Any]) -> None:
        """Update install progress on event."""
        progress: NodeFirmwareUpdateProgress = event["firmware_update_progress"]
        if not self._latest_version_firmware:
            return
        self._attr_in_progress = int(progress.progress)
        self.async_write_ha_state()

    @callback
    def _update_finished(self, event: dict[str, Any]) -> None:
        """Update install progress on event."""
        result: NodeFirmwareUpdateResult = event["firmware_update_finished"]
        self._result = result
        self._finished_event.set()

    @callback
    def _unsub_firmware_events_and_reset_progress(
        self, write_state: bool = True
    ) -> None:
        """Unsubscribe from firmware events and reset update install progress."""
        if self._progress_unsub:
            self._progress_unsub()
            self._progress_unsub = None

        if self._finished_unsub:
            self._finished_unsub()
            self._finished_unsub = None

        self._result = None
        self._finished_event.clear()
        self._attr_in_progress = False
        if write_state:
            self.async_write_ha_state()

    async def _async_update(self, _: HomeAssistant | datetime | None = None) -> None:
        """Update the entity."""
        self._poll_unsub = None

        # If device is asleep/dead, wait for it to wake up/become alive before
        # attempting an update
        for status, event_name in (
            (NodeStatus.ASLEEP, "wake up"),
            (NodeStatus.DEAD, "alive"),
        ):
            if self.node.status == status:
                if not self._status_unsub:
                    self._status_unsub = self.node.once(
                        event_name, self._update_on_status_change
                    )
                return

        try:
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
                and AwesomeVersion(latest_firmware.version)
                > AwesomeVersion(self.node.firmware_version)
            ):
                self._latest_version_firmware = latest_firmware
                self._attr_latest_version = latest_firmware.version
                self.async_write_ha_state()
            elif self._attr_latest_version != self._attr_installed_version:
                self._attr_latest_version = self._attr_installed_version
                self.async_write_ha_state()
        finally:
            self._poll_unsub = async_call_later(
                self.hass, timedelta(days=1), self._async_update
            )

    async def async_release_notes(self) -> str | None:
        """Get release notes."""
        if self._latest_version_firmware is None:
            return None
        return self._latest_version_firmware.changelog

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        firmware = self._latest_version_firmware
        assert firmware
        self._unsub_firmware_events_and_reset_progress(False)
        self._attr_in_progress = True
        self.async_write_ha_state()

        self._progress_unsub = self.node.on(
            "firmware update progress", self._update_progress
        )
        self._finished_unsub = self.node.on(
            "firmware update finished", self._update_finished
        )

        try:
            await self.driver.controller.async_firmware_update_ota(
                self.node, firmware.files
            )
        except BaseZwaveJSServerError as err:
            self._unsub_firmware_events_and_reset_progress()
            raise HomeAssistantError(err) from err

        # We need to block until we receive the `firmware update finished` event
        await self._finished_event.wait()
        assert self._result is not None

        # If the update was not successful, we should throw an error
        # to let the user know
        if not self._result.success:
            error_msg = self._result.status.name.replace("_", " ").title()
            self._unsub_firmware_events_and_reset_progress()
            raise HomeAssistantError(error_msg)

        # If we get here, all files were installed successfully
        self._attr_installed_version = self._attr_latest_version = firmware.version
        self._latest_version_firmware = None
        self._unsub_firmware_events_and_reset_progress()

    async def async_poll_value(self, _: bool) -> None:
        """Poll a value."""
        LOGGER.error(
            "There is no value to refresh for this entity so the zwave_js.refresh_value"
            " service won't work for it"
        )

    async def async_added_to_hass(self) -> None:
        """Call when entity is added."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self.unique_id}_poll_value",
                self.async_poll_value,
            )
        )

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._base_unique_id}_remove_entity",
                self.async_remove,
            )
        )

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._base_unique_id}_remove_entity_on_ready_node",
                self.async_remove,
            )
        )

        self.async_on_remove(async_at_start(self.hass, self._async_update))

    async def async_will_remove_from_hass(self) -> None:
        """Call when entity will be removed."""
        if self._status_unsub:
            self._status_unsub()
            self._status_unsub = None

        if self._poll_unsub:
            self._poll_unsub()
            self._poll_unsub = None

        self._unsub_firmware_events_and_reset_progress(False)
