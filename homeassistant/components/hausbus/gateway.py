"""Representation of a Haus-Bus gateway."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
import logging
import time
from typing import Any

from pyhausbus.ABusFeature import ABusFeature
from pyhausbus.BusDataMessage import BusDataMessage
from pyhausbus.de.hausbus.homeassistant.proxy.Controller import Controller, EIndex
from pyhausbus.de.hausbus.homeassistant.proxy.controller.data.Configuration import (
    Configuration,
)
from pyhausbus.de.hausbus.homeassistant.proxy.controller.data.ModuleId import ModuleId
from pyhausbus.de.hausbus.homeassistant.proxy.controller.data.RemoteObjects import (
    RemoteObjects,
)
from pyhausbus.HomeServer import HomeServer
from pyhausbus.IBusDataListener import IBusDataListener
from pyhausbus.ObjectId import ObjectId

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .cover import HausbusCover, Rollladen
from .entity import HausbusEntity

LOGGER = logging.getLogger(__name__)


class HausbusGateway(IBusDataListener):
    """Manages a Haus-Bus gateway."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the system."""

        self.hass = hass
        self.config_entry = config_entry
        self.devices: dict[int, str] = {}  # maps device_id and hass entry id
        self.channels: dict[int, HausbusEntity] = {}  # maps object_id and entities
        self.automatic_get_module_id_time: dict[
            int, float
        ] = {}  # controls automatic device settings reading
        self.home_server = HomeServer()
        self.home_server.addBusEventListener(self)

        # callbacks to dynamically register new entities discovered by this gateway
        self._new_channel_listeners: dict[
            str, Callable[[HausbusEntity], Coroutine[Any, Any, None]]
        ] = {}

    async def start_discovery(self):
        """Starts device discovery."""

        async def discovery_callback():
            LOGGER.debug("Search devices")
            self.hass.async_add_executor_job(self.home_server.searchDevices)

        await discovery_callback()

    def add_channel(self, instance: ABusFeature) -> None:
        """Add a new Haus-Bus Channel to this gateway's channel list."""

        object_id = instance.getObjectId()

        if object_id not in self.channels:
            new_channel = None

            # COVER
            if isinstance(instance, Rollladen):
                device_info = self.get_device_info(ObjectId(object_id).getDeviceId())
                new_channel = HausbusCover(instance, device_info)
                new_domain = COVER_DOMAIN
            else:
                return

            if new_channel is not None:
                LOGGER.debug("create %s channel for %s", new_domain, instance)
                self.channels[object_id] = new_channel
                asyncio.run_coroutine_threadsafe(
                    self._new_channel_listeners[new_domain](new_channel), self.hass.loop
                ).result()
                new_channel.get_hardware_status()

    def busDataReceived(self, busDataMessage: BusDataMessage) -> None:
        """Handle Haus-Bus messages."""

        object_id = ObjectId(busDataMessage.getSenderObjectId())
        device_id = object_id.getDeviceId()
        data = busDataMessage.getData()

        # ignore messages from own server
        if self.home_server.is_internal_device(device_id):
            return

        LOGGER.debug("busDataReceived: data %s from %s", data, object_id)

        # with received ModuleId add to devices
        if isinstance(data, ModuleId):
            LOGGER.debug("got moduleId of %s with data: %s", device_id, data)

            if device_id not in self.devices:
                self.devices[device_id] = "new_device"
            return

        device = self.devices.get(device_id)

        # Request module_id for unknown devices
        if device is None:
            LOGGER.debug("got event of unknown device %s", device_id)

            if device_id != 0 and not self.was_automatic_get_module_id_already_sent(
                device_id
            ):
                LOGGER.debug("-> calling getModuleId")
                Controller.create(device_id, 1).getModuleId(EIndex.RUNNING)
            return

        # With received configuration add device to hass registry
        if isinstance(data, Configuration):
            LOGGER.debug("got configuration of %s with data: %s", device_id, data)

            asyncio.run_coroutine_threadsafe(
                self.async_create_device_registry(device_id), self.hass.loop
            ).result()
            return

        # with received remoteObjects update channels
        if isinstance(data, RemoteObjects):
            LOGGER.debug(
                "got remoteObjects of %s with data: %s", object_id.getDeviceId(), data
            )

            instances: list[ABusFeature] = self.home_server.getHomeassistantChannels(
                device_id, data
            )

            for instance in instances:
                LOGGER.debug(
                    "adding channel for device %s: %s",
                    object_id.getDeviceId(),
                    instance.getName(),
                )
                self.add_channel(instance)
            return

        channel = self.channels.get(object_id.getValue())

        # pass events to corresponding channel
        if isinstance(channel, HausbusEntity):
            LOGGER.debug("handle_event %s %s", channel, data)
            channel.handle_event(data)
        else:
            LOGGER.debug("no corresponding channel")

    def register_platform_add_channel_callback(
        self,
        add_channel_callback: Callable[[HausbusEntity], Coroutine[Any, Any, None]],
        platform: str,
    ) -> None:
        """Register add channel callbacks."""
        self._new_channel_listeners[platform] = add_channel_callback

    async def async_create_device_registry(self, device_id: int):
        """Creates a device in the hass registry."""

        device_registry = dr.async_get(self.hass)
        device_info = self.get_device_info(device_id)

        device_entry = device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers={(DOMAIN, str(device_id))},
            manufacturer=device_info.get("manufacturer"),
            model=device_info.get("model"),
            name=device_info.get("name"),
        )
        LOGGER.debug(
            "hassEntryId = %s, device_id = %s, manufacturer = %s, model = %s, name = %s",
            device_entry.id,
            str(device_id),
            device_info.get("manufacturer"),
            device_info.get("model"),
            device_info.get("name"),
        )
        self.devices[device_id] = device_entry.id

    def get_device_info(self, device_id: int):
        """Creates a device info for the given device_id."""

        module = self.home_server.get_module_id_from_cache(device_id)
        model = self.home_server.get_model(device_id)
        name = f"{model} {device_id}"
        software_version = (
            module.getFirmwareId().getTemplateId()
            + " "
            + str(module.getMajorRelease())
            + "."
            + str(module.getMinorRelease())
        )
        hardware_version = module.getName()

        return DeviceInfo(
            identifiers={(DOMAIN, str(device_id))},
            manufacturer="HausBus",
            model=model,
            name=name,
            sw_version=software_version,
            hw_version=hardware_version,
        )

    def was_automatic_get_module_id_already_sent(self, device_id: int) -> bool:
        """Checks if an automatic get_module_id call makes sense."""
        now = time.time()
        last_time = self.automatic_get_module_id_time.get(device_id)

        if last_time is not None and now - last_time < 60:
            LOGGER.debug(
                "no automatic get_module_id to %s because done before %.1f s",
                device_id,
                now - last_time,
            )
            return True

        self.automatic_get_module_id_time[device_id] = now
        return False
