"""Representation of a Haus-Bus gateway."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
import logging
import re
import time
from typing import Any, cast

from pyhausbus.ABusFeature import ABusFeature
from pyhausbus.BusDataMessage import BusDataMessage
from pyhausbus.de.hausbus.homeassistant.proxy import ProxyFactory
from pyhausbus.de.hausbus.homeassistant.proxy.Controller import Controller, EIndex
from pyhausbus.de.hausbus.homeassistant.proxy.controller.data.Configuration import (
    Configuration,
)
from pyhausbus.de.hausbus.homeassistant.proxy.controller.data.ModuleId import ModuleId
from pyhausbus.de.hausbus.homeassistant.proxy.controller.data.RemoteObjects import (
    RemoteObjects,
)
from pyhausbus.HausBusUtils import HOMESERVER_DEVICE_ID
from pyhausbus.HomeServer import HomeServer
from pyhausbus.IBusDataListener import IBusDataListener
from pyhausbus.ObjectId import ObjectId
from pyhausbus.Templates import Templates

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .cover import HausbusCover, Rollladen
from .device import HausbusDevice
from .entity import HausbusEntity

DOMAIN = "hausbus"

LOGGER = logging.getLogger(__name__)


class HausbusGateway(IBusDataListener):
    """Manages a Haus-Bus gateway."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the system."""
        self.hass = hass
        self.config_entry = config_entry
        self.devices: dict[str, HausbusDevice] = {}
        self.channels: dict[str, dict[tuple[str, str], HausbusEntity]] = {}
        self.automatic_get_module_id_time: dict[int, float] = {}
        self.home_server = HomeServer()
        self.home_server.addBusEventListener(self)
        self._new_channel_listeners: dict[
            str, Callable[[HausbusEntity], Coroutine[Any, Any, None]]
        ] = {}

    async def createDiscoveryButton(self):
        """Creates a Button to manually start device discovery."""

        async def discovery_callback():
            LOGGER.debug("Search devices")
            self.hass.async_add_executor_job(self.home_server.searchDevices)

        await discovery_callback()

    def add_device(self, device_id: str, module: ModuleId) -> None:
        """Add a new Haus-Bus Device to this gateway's device list."""
        if device_id not in self.devices:
            self.devices[device_id] = HausbusDevice(
                device_id,
                module.getFirmwareId().getTemplateId()
                + " "
                + str(module.getMajorRelease())
                + "."
                + str(module.getMinorRelease()),
                module.getName(),
                module.getFirmwareId(),
            )

        if device_id not in self.channels:
            self.channels[device_id] = {}

    def get_device(self, object_id: ObjectId) -> HausbusDevice | None:
        """Get the device referenced by ObjectId from the devices list."""
        return self.devices.get(str(object_id.getDeviceId()))

    def get_channel_list(
        self, object_id: ObjectId
    ) -> dict[tuple[str, str], HausbusEntity] | None:
        """Get the channel list of a device referenced by ObjectId."""
        return self.channels.get(str(object_id.getDeviceId()))

    def get_channel_id(self, object_id: ObjectId) -> tuple[str, str]:
        """Get the channel identifier from an ObjectId."""
        return (str(object_id.getClassId()), str(object_id.getInstanceId()))

    def get_channel(self, object_id: ObjectId) -> HausbusEntity | None:
        """Get channel for to a ObjectId."""
        channels = self.get_channel_list(object_id)
        if channels is not None:
            channel_id = self.get_channel_id(object_id)
            return channels.get(channel_id)
        return None

    def add_channel(self, instance: ABusFeature) -> None:
        """Add a new Haus-Bus Channel to this gateway's channel list."""

        object_id = ObjectId(instance.getObjectId())
        device = self.get_device(object_id)
        channel_list = self.get_channel_list(object_id)

        if (
            device is not None
            and channel_list is not None
            and self.get_channel_id(object_id) not in channel_list
        ):
            new_channel = None

            # COVER
            if isinstance(instance, Rollladen):
                new_channel = HausbusCover(instance, device)
                new_domain = COVER_DOMAIN
            else:
                return

            if new_channel is not None:
                LOGGER.debug("create %s channel for %s", new_domain, instance)
                channel_list[self.get_channel_id(object_id)] = new_channel
                asyncio.run_coroutine_threadsafe(
                    self._new_channel_listeners[new_domain](new_channel), self.hass.loop
                ).result()
                new_channel.get_hardware_status()

    def busDataReceived(self, busDataMessage: BusDataMessage) -> None:
        """Handle Haus-Bus messages."""

        object_id = ObjectId(busDataMessage.getSenderObjectId())
        data = busDataMessage.getData()
        deviceId = object_id.getDeviceId()
        templates = Templates.get_instance()

        # ignore messages sent from this module
        if deviceId in {HOMESERVER_DEVICE_ID, 9999, 12222}:
            return

        LOGGER.debug("busDataReceived with data = %s from %s", data, object_id)

        controller = Controller(object_id.getValue())

        # ModuleId -> getConfiguration
        if isinstance(data, ModuleId):
            LOGGER.debug(
                "got moduleId of %s with data: %s", object_id.getDeviceId(), data
            )
            self.add_device(str(object_id.getDeviceId()), data)
            controller.getConfiguration()
            return

        # Bei unbekanntem Gerät -> ModuleId abfragen
        device = self.get_device(object_id)
        if device is None:
            LOGGER.debug(
                "got event of unknown device %s with data: %s",
                object_id.getDeviceId(),
                data,
            )
            if not self.was_automatic_get_module_id_already_sent(deviceId):
                LOGGER.debug("-> calling getModuleId")
                controller.getModuleId(EIndex.RUNNING)
            return

        # Configuration -> getRemoteObjects
        if isinstance(data, Configuration):
            LOGGER.debug(
                "got configuration of %s with data: %s", object_id.getDeviceId(), data
            )
            config = cast(Configuration, data)
            device = self.get_device(object_id)
            if device is not None:
                device.set_config(config)

                # Mit der Konfiguration registrieren wir das Device bei HASS
                asyncio.run_coroutine_threadsafe(
                    self.async_create_device_registry(device), self.hass.loop
                ).result()

                controller.getRemoteObjects()
                return

        # RemoteObjects -> Channel anlegen
        if isinstance(data, RemoteObjects):
            LOGGER.debug(
                "got remoteObjects of %s with data: %s", object_id.getDeviceId(), data
            )

            device = self.get_device(object_id)
            if device is not None:
                instances: list[ABusFeature] = self.home_server.getDeviceInstances(
                    object_id.getValue(), data
                )

                for instance in instances:
                    instanceObjectId = ObjectId(instance.getObjectId())
                    name = templates.get_feature_name_from_template(
                        device.firmware_id,
                        device.fcke,
                        instanceObjectId.getClassId(),
                        instanceObjectId.getInstanceId(),
                    )

                    LOGGER.debug(
                        "name for firmwareId %s, fcke: %s, classId %s, instanceId %s is %s",
                        device.firmware_id,
                        device.fcke,
                        instanceObjectId.getClassId(),
                        instanceObjectId.getInstanceId(),
                        name,
                    )

                    if deviceId in (29725, 22784):
                      className = ProxyFactory.getBusClassNameForClass(
                        instanceObjectId.getClassId()
                      ).rsplit(".", 1)[-1]
                      name = f"{className} {instanceObjectId.getInstanceId()}"
                      LOGGER.debug("specialName %s", name)

                    if name is None:
                        className = ProxyFactory.getBusClassNameForClass(
                            instanceObjectId.getClassId()
                        ).rsplit(".", 1)[-1]

                        name = {
                            "Temperatursensor": f"Temperatursensor {instanceObjectId.getInstanceId()}",
                            "Feuchtesensor": f"Feuchtesensor {instanceObjectId.getInstanceId()}",
                            "Helligkeitssensor": f"Helligkeitssensor {instanceObjectId.getInstanceId()}",
                            "RFIDReader": f"RFIDReader {instanceObjectId.getInstanceId()}",
                            "Drucksensor": f"Drucksensor {instanceObjectId.getInstanceId()}",
                            "PT1000": f"PT1000 {instanceObjectId.getInstanceId()}",
                        }.get(className)

                    if name is not None:
                        instance.setName(name)
                        self.add_channel(instance)

                return

        if device is not None:
            # Alles andere wird an die jeweiligen Channel weitergeleitet
            channel = self.get_channel(object_id)

            # all channel events
            if isinstance(channel, HausbusEntity):
                LOGGER.debug("handle_event %s %s", channel, data)
                channel.handle_event(data)
            else:
                LOGGER.debug("kein zugehöriger channel")

    def register_platform_add_channel_callback(
        self,
        add_channel_callback: Callable[[HausbusEntity], Coroutine[Any, Any, None]],
        platform: str,
    ) -> None:
        """Register add channel callbacks."""
        self._new_channel_listeners[platform] = add_channel_callback

    def extract_final_number(self, text: str) -> int | None:
        """Extract a number from the end of the given string."""
        match = re.search(r"(\d+)$", text.strip())
        if match:
            return int(match.group(1))
        return None

    async def async_update_device_registry(self, device: HausbusDevice):
        """Updates the device name in the hass registry."""
        device_registry = dr.async_get(self.hass)
        device_entry = device_registry.async_update_device(
            device.hass_device_entry_id, name=device.name
        )

        if device_entry is not None:
            LOGGER.debug("updated hassEntryId = %s", device_entry.id)
        else:
            LOGGER.debug(
                "device_entry is none for hass_device_entry_id %s",
                device.hass_device_entry_id,
            )

    async def async_create_device_registry(self, device: HausbusDevice):
        """Creates a device in the hass registry."""
        device_registry = dr.async_get(self.hass)
        device_entry = device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers={(DOMAIN, device.device_id)},
            manufacturer="HausBus",
            model=device.model_id,
            name=device.name,
        )
        LOGGER.debug("hassEntryId = %s", device_entry.id)
        device.set_hass_device_entry_id(device_entry.id)

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

    async def removeDevice(self, device_id: str):
        """Removes a device from the integration."""
        LOGGER.debug("delete device %s", device_id)
        for hausBusDevice in self.devices.values():
            if hausBusDevice.device_id == device_id:
                LOGGER.debug("found delete device %s", hausBusDevice)
                del self.devices[device_id]
                del self.channels[device_id]
                to_delete = [
                    objectIdInt
                    for objectIdInt, hausBusEntity in self.events.items()
                    if str(ObjectId(objectIdInt).getDeviceId()) == device_id
                ]

                for key in to_delete:
                    del self.events[key]
                return True

        return True

    def resetDevice(self, device_id: str):
        """Resets a Device."""
        LOGGER.debug("reset device %s", device_id)

        for hausBusDevice in self.devices.values():
            if hausBusDevice.hass_device_entry_id == device_id:
                device_id_int = int(hausBusDevice.device_id)
                LOGGER.debug("resetting device %s", device_id_int)
                Controller.create(device_id_int, 1).reset()
                return True
        return False


# pre-commit: skip=codespell
