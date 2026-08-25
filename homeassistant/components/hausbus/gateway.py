"""Representation of a Haus-Bus gateway."""

import asyncio
import logging
from typing import TYPE_CHECKING

from pyhausbus.ABusFeature import ABusFeature
from pyhausbus.BusDataMessage import BusDataMessage
from pyhausbus.de.hausbus.homeassistant.proxy.controller.data.Configuration import (
    Configuration,
)
from pyhausbus.de.hausbus.homeassistant.proxy.controller.data.ModuleId import ModuleId
from pyhausbus.HomeServer import HomeServer
from pyhausbus.IBusDataListener import IBusDataListener
from pyhausbus.ObjectId import ObjectId

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, NEW_CHANNEL_ADDED

if TYPE_CHECKING:
    from . import HausbusConfigEntry

LOGGER = logging.getLogger(__name__)


class HausbusGateway(IBusDataListener):
    """Manages a Haus-Bus gateway."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HausbusConfigEntry,
        home_server: HomeServer,
    ) -> None:
        """Initialize the system."""
        self.hass = hass
        self.config_entry = config_entry
        self.home_server = home_server
        self.home_server.addBusEventListener(self)
        self.home_server.addBusDeviceListener(self)

        # to prevent duplicate channels but to allow to add channels even if it was registered before
        self.registered_channels: set[int] = set()
        self.discovery_task: asyncio.Task[None] | None = None

    @classmethod
    async def async_create(
        cls, hass: HomeAssistant, config_entry: HausbusConfigEntry
    ) -> HausbusGateway:
        """Create the gateway, opening the Haus-Bus network connection."""
        home_server = await hass.async_add_executor_job(HomeServer)
        return cls(hass, config_entry, home_server)

    async def start_discovery(self) -> None:
        """Start device discovery."""
        LOGGER.debug("Search devices")
        await self.hass.async_add_executor_job(self.home_server.searchDevices)

    def newDeviceDetected(
        self,
        device_id: int,
        model_type: str | None,
        module_id: ModuleId,
        configuration: Configuration,
        channels: list[ABusFeature],
    ) -> None:
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

        asyncio.run_coroutine_threadsafe(
            self.async_register_device(device_id, device_info), self.hass.loop
        ).result(timeout=10)

        for channel in channels:
            object_id = channel.getObjectId()
            if object_id not in self.registered_channels:
                self.registered_channels.add(object_id)
                self.hass.loop.call_soon_threadsafe(
                    async_dispatcher_send,
                    self.hass,
                    NEW_CHANNEL_ADDED,
                    channel,
                    device_info,
                )

    def busDataReceived(self, busDataMessage: BusDataMessage) -> None:
        """Handle Haus-Bus messages."""
        object_id = ObjectId(busDataMessage.getSenderObjectId())
        device_id = object_id.getDeviceId()
        data = busDataMessage.getData()

        # ignore messages from own server
        if self.home_server.is_internal_device(device_id):
            return

        LOGGER.debug("busDataReceived: data %s from %s", data, object_id)

        self.hass.loop.call_soon_threadsafe(
            async_dispatcher_send,
            self.hass,
            f"hausbus_update_{object_id.getValue()}",
            data,
        )

    async def async_register_device(
        self, device_id: int, device_info: DeviceInfo
    ) -> None:
        """Create a device in the hass registry."""
        device_registry = dr.async_get(self.hass)

        device = device_registry.async_get_device(
            identifiers={(DOMAIN, str(device_id))},
            connections=None,
        )

        if device is not None:
            LOGGER.debug("device %s already registered", device_id)
            return

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
