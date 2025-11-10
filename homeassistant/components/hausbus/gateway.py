"""Representation of a Haus-Bus gateway."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
import logging
from typing import Any

from pyhausbus.ABusFeature import ABusFeature
from pyhausbus.BusDataMessage import BusDataMessage
from pyhausbus.de.hausbus.homeassistant.proxy.controller.data.Configuration import (
    Configuration,
)
from pyhausbus.de.hausbus.homeassistant.proxy.controller.data.ModuleId import ModuleId
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
        self.channels: dict[int, HausbusEntity] = {}  # maps object_id and entities

        self.home_server = HomeServer()
        self.home_server.addBusEventListener(self)
        self.home_server.addBusDeviceListener(self)

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

    def newDeviceDetected(
        self,
        device_id: int,
        model_type: str,
        module_id: ModuleId,
        configuration: Configuration,
        channels: list[ABusFeature],
    ):
        """Handle new discovered Haus-Bus device."""
        LOGGER.debug(
            "newDeviceDetected: device_id %s model_type %s module_id %s configuration %s",
            device_id,
            model_type,
            module_id,
            configuration,
        )

        device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device_id))},
            manufacturer="HausBus",
            model=model_type,
            name=f"{model_type} {device_id}",
            sw_version=module_id.getFirmwareId().getTemplateId()
            + " "
            + str(module_id.getMajorRelease())
            + " "
            + str(module_id.getMinorRelease()),
            hw_version=module_id.getName(),
        )

        # register device
        asyncio.run_coroutine_threadsafe(
            self.async_create_device_registry(device_id, device_info), self.hass.loop
        ).result()

        for channel in channels:
            LOGGER.debug(
                "device %s reported channel %s",
                device_id,
                channel.getName(),
            )
            self.add_channel(channel, device_info)

    def add_channel(self, instance: ABusFeature, device_info: DeviceInfo) -> None:
        """Create HA entity for provided device channel."""

        object_id = instance.getObjectId()

        if object_id not in self.channels:
            new_channel = None

            # COVER
            if isinstance(instance, Rollladen):
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
            else:
                LOGGER.debug("no entity created for %s", instance)

    def busDataReceived(self, busDataMessage: BusDataMessage) -> None:
        """Handle Haus-Bus messages."""

        object_id = ObjectId(busDataMessage.getSenderObjectId())
        device_id = object_id.getDeviceId()
        data = busDataMessage.getData()

        # ignore messages from own server
        if self.home_server.is_internal_device(device_id):
            return

        LOGGER.debug("busDataReceived: data %s from %s", data, object_id)

        # pass events to corresponding channel
        channel = self.channels.get(object_id.getValue())

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

    async def async_create_device_registry(
        self, device_id: int, device_info: DeviceInfo
    ):
        """Creates a device in the hass registry."""

        device_registry = dr.async_get(self.hass)

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
