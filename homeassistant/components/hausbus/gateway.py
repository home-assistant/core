"""Representation of a Haus-Bus gateway."""

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, cast

from pyhausbus.ABusFeature import ABusFeature
from pyhausbus.BusDataMessage import BusDataMessage
from pyhausbus.de.hausbus.homeassistant.proxy.Controller import Controller
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

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .channel import HausbusChannel
from .device import HausbusDevice
from .event_handler import IEventHandler
from .light import HausbusLight


class HausbusGateway(IBusDataListener, IEventHandler):
    """Manages a single Haus-Bus gateway."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the system."""
        self.hass = hass
        self.config_entry = config_entry
        self.bridge_id = "1"
        self.devices: dict[str, HausbusDevice] = {}
        self.channels: dict[str, dict[tuple[str, str], HausbusChannel]] = {}
        self.home_server = HomeServer()
        self.home_server.addBusEventListener(self)
        self._new_channel_listeners: dict[
            str, Callable[[HausbusChannel], Coroutine[Any, Any, None]]
        ] = {}

    def add_device(self, device_id: str, module: ModuleId):
        """Add a new Haus-Bus Device to this gateways devices list."""
        device = HausbusDevice(
            self.bridge_id,
            device_id,
            module.getFirmwareId().getTemplateId()
            + " "
            + str(module.getMajorRelease())
            + "."
            + str(module.getMinorRelease()),
            module.getName(),
            module.getFirmwareId(),
        )
        if device_id not in self.devices:
            self.devices[device_id] = device
        if device_id not in self.channels:
            self.channels[device_id] = {}

    def get_device(self, object_id: ObjectId) -> HausbusDevice:
        """Get the device referenced by ObjectId from the devices list."""
        return self.devices[str(object_id.getDeviceId())]

    def get_channel_list(
        self, object_id: ObjectId
    ) -> dict[tuple[str, str], HausbusChannel]:
        """Get the channel list of a device referenced by ObjectId."""
        return self.channels[str(object_id.getDeviceId())]

    def get_channel_id(self, object_id: ObjectId) -> tuple[str, str]:
        """Get the channel identifier from an ObjectId."""
        return (str(object_id.getClassId()), str(object_id.getInstanceId()))

    def get_channel(self, object_id: ObjectId) -> HausbusChannel | None:
        """Get channel from channel list."""
        channels = self.get_channel_list(object_id)
        channel_id = self.get_channel_id(object_id)
        return channels.get(channel_id, None)

    def add_light_channel(self, instance: ABusFeature, object_id: ObjectId):
        """Add a new Haus-Bus Light Channel to this gateways channel list."""
        light = HausbusLight(
            object_id.getInstanceId(),
            self.get_device(object_id),
            instance,
        )
        self.get_channel_list(object_id)[self.get_channel_id(object_id)] = light
        asyncio.run_coroutine_threadsafe(
            self._new_channel_listeners[LIGHT_DOMAIN](light), self.hass.loop
        ).result()

    def add_channel(self, instance: ABusFeature):
        """Add a new Haus-Bus Channel to this gateways channel list."""
        object_id = ObjectId(instance.getObjectId())
        if self.get_channel_id(object_id) not in self.get_channel_list(object_id):
            if HausbusLight.is_light_channel(object_id.getClassId()):
                self.add_light_channel(instance, object_id)

    def busDataReceived(self, busDataMessage: BusDataMessage):
        """Handle Haus-Bus messages."""
        object_id = ObjectId(busDataMessage.getSenderObjectId())
        data = busDataMessage.getData()

        if object_id.getDeviceId() == 9998:
            # ignore messages sent from this module
            return

        controller = Controller(object_id.getValue())

        if isinstance(data, ModuleId):
            self.add_device(
                str(object_id.getDeviceId()),
                data,
            )
            controller.getConfiguration()
        if isinstance(data, Configuration):
            config = cast(Configuration, data)
            device = self.get_device(object_id)
            device.set_type(config.getFCKE())
            controller.getRemoteObjects()
        if isinstance(data, RemoteObjects):
            instances: list[ABusFeature] = self.home_server.getDeviceInstances(
                object_id.getValue(), data
            )
            for instance in instances:
                # handle channels for the sending device
                self.add_channel(instance)
        # light event handling
        channel = self.get_channel(object_id)
        if channel is not None:
            HausbusLight.handle_light_event(data, channel)

    def register_platform_add_channel_callback(
        self,
        add_channel_callback: Callable[[HausbusChannel], Coroutine[Any, Any, None]],
        platform: str,
    ):
        """Register add channel callbacks."""
        self._new_channel_listeners[platform] = add_channel_callback
