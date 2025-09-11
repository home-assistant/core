"""Representation of a Haus-Bus gateway."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
import logging
import re
import time
from typing import Any, cast

from custom_components.hausbus.number import HausbusControl
from custom_components.hausbus.sensor import HausbusPowerMeter, HausbusRfidSensor
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
from pyhausbus.de.hausbus.homeassistant.proxy.PowerMeter import PowerMeter
from pyhausbus.de.hausbus.homeassistant.proxy.RFIDReader import RFIDReader
from pyhausbus.de.hausbus.homeassistant.proxy.rFIDReader.data.EvData import (
    EvData as RfidEvData,
)
from pyhausbus.de.hausbus.homeassistant.proxy.Taster import Taster
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvClicked import EvClicked
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvCovered import EvCovered
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvDoubleClick import (
    EvDoubleClick,
)
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvFree import EvFree
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvHoldEnd import EvHoldEnd
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvHoldStart import EvHoldStart
from pyhausbus.HausBusUtils import HOMESERVER_DEVICE_ID
from pyhausbus.HomeServer import HomeServer
from pyhausbus.IBusDataListener import IBusDataListener
from pyhausbus.ObjectId import ObjectId
from pyhausbus.Templates import Templates

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .binary_sensor import HausbusBinarySensor
from .button import HausbusButton
from .cover import HausbusCover, Rollladen
from .device import HausbusDevice
from .entity import HausbusEntity
from .event import HausBusEvent
from .light import (
    Dimmer,
    HausbusBackLight,
    HausbusDimmerLight,
    HausbusLedLight,
    HausbusRGBDimmerLight,
    Led,
    LogicalButton,
    RGBDimmer,
)

# from .number import HausBusNumber
from .sensor import (
    AnalogEingang,
    Feuchtesensor,
    HausbusAnalogEingang,
    HausbusBrightnessSensor,
    HausbusHumiditySensor,
    HausbusTemperaturSensor,
    Helligkeitssensor,
    Temperatursensor,
)
from .switch import HausbusSwitch, Schalter

DOMAIN = "hausbus"

LOGGER = logging.getLogger(__name__)


class HausbusGateway(IBusDataListener):  # type: ignore[misc]
    """Manages a Haus-Bus gateway."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the system."""
        self.hass = hass
        self.config_entry = config_entry
        self.devices: dict[str, HausbusDevice] = {}
        self.channels: dict[str, dict[tuple[str, str], HausbusEntity]] = {}
        self.events: dict[int, HausBusEvent] = {}
        self.automatic_get_module_id_time: dict[int, float] = {}
        self.home_server = HomeServer()
        self.home_server.addBusEventListener(self)
        self._new_channel_listeners: dict[
            str, Callable[[HausbusEntity], Coroutine[Any, Any, None]]
        ] = {}

        # Listener für state_changed registrieren
        # self.hass.bus.async_listen("state_changed", self._state_changed_listener)

        # asyncio.run_coroutine_threadsafe(self.async_delete_devices(), self.hass.loop)

    async def createDiscoveryButtonAndStartDiscovery(self):
        """Creates a Button to manually start device discovery and starts discovery."""

        async def discovery_callback():
            LOGGER.debug("Search devices")
            self.hass.async_add_executor_job(self.home_server.searchDevices)

        self.addStandaloneButton(
            "hausbus_discovery_button", "Discover Haus-Bus Devices", discovery_callback
        )
        await discovery_callback()

    def addStandaloneButton(
        self,
        uniqueId: str,
        name: str,
        callback: Callable[[], Coroutine[Any, Any, None]],
    ):
        """Creates a Button that calls a method."""
        asyncio.run_coroutine_threadsafe(
            self._new_channel_listeners[BUTTON_DOMAIN](
                HausbusButton(uniqueId, name, callback)
            ),
            self.hass.loop,
        )

    def add_device(self, device_id: str, module: ModuleId) -> None:
        """Add a new Haus-Bus Device to this gateway's device list."""
        if device_id not in self.devices:
            self.devices[device_id] = HausbusDevice(
                device_id,
                module.getFirmwareId().getTemplateId()
                +" "
                +str(module.getMajorRelease())
                +"."
                +str(module.getMinorRelease()),
                module.getName(),
                module.getFirmwareId(),
            )

        if device_id not in self.channels:
            self.channels[device_id] = {}

    def get_device(self, object_id: ObjectId) -> HausbusDevice | None:
        """Get the device referenced by ObjectId from the devices list."""
        return self.devices.get(str(object_id.getDeviceId()))

    def get_event_entity(self, object_id: int) -> HausBusEvent | None:
        """Get the event referenced by ObjectId."""
        return self.events.get(object_id)

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

            # Specials
            if (
                device.is_leistungs_regler()
                and isinstance(instance, Schalter)
                and "Rote Modul LED" not in instance.getName()
            ):
                new_channel = HausbusControl(instance, device)
                new_domain = NUMBER_DOMAIN
            # LIGHT
            elif isinstance(instance, Dimmer):
                new_channel = HausbusDimmerLight(instance, device)
                new_domain = LIGHT_DOMAIN
            elif isinstance(instance, Led):
                new_channel = HausbusLedLight(instance, device)
                new_domain = LIGHT_DOMAIN
            elif isinstance(instance, LogicalButton):
                new_channel = HausbusBackLight(instance, device)
                new_domain = LIGHT_DOMAIN
            elif isinstance(instance, RGBDimmer):
                new_channel = HausbusRGBDimmerLight(instance, device)
                new_domain = LIGHT_DOMAIN
            # SWITCH
            elif isinstance(instance, Schalter):
                new_channel = HausbusSwitch(instance, device)
                new_domain = SWITCH_DOMAIN
            # COVER
            elif isinstance(instance, Rollladen):
                new_channel = HausbusCover(instance, device)
                new_domain = COVER_DOMAIN
            # SENSOR
            elif isinstance(instance, Temperatursensor):
                new_channel = HausbusTemperaturSensor(instance, device)
                new_domain = SENSOR_DOMAIN
            elif isinstance(instance, Helligkeitssensor):
                new_channel = HausbusBrightnessSensor(instance, device)
                new_domain = SENSOR_DOMAIN
            elif isinstance(instance, Feuchtesensor):
                new_channel = HausbusHumiditySensor(instance, device)
                new_domain = SENSOR_DOMAIN
            elif isinstance(instance, AnalogEingang):
                new_channel = HausbusAnalogEingang(instance, device)
                new_domain = SENSOR_DOMAIN
            elif isinstance(instance, PowerMeter):
                new_channel = HausbusPowerMeter(instance, device)
                new_domain = SENSOR_DOMAIN
            elif isinstance(instance, RFIDReader):
                new_channel = HausbusRfidSensor(instance, device)
                new_domain = SENSOR_DOMAIN
            elif isinstance(instance, Taster):
                # if not instance.getName().startswith("Taster"):
                new_channel = HausbusBinarySensor(instance, device)
                new_domain = BINARY_SENSOR_DOMAIN
            else:
                return

            if new_channel is not None:
                LOGGER.debug("create %s channel for %s", new_domain, instance)
                channel_list[self.get_channel_id(object_id)] = new_channel
                asyncio.run_coroutine_threadsafe(
                    self._new_channel_listeners[new_domain](new_channel), self.hass.loop
                ).result()
                new_channel.get_hardware_status()

            # additional EventEnties for all binary inputs and pushbuttons
            if (
                isinstance(instance, Taster)
                and self.get_event_entity(instance.getObjectId()) is None
            ):
                LOGGER.debug("create event channel for %s", instance)
                new_channel = HausBusEvent(instance, device)
                self.events[instance.getObjectId()] = new_channel
                asyncio.run_coroutine_threadsafe(
                    self._new_channel_listeners["EVENTS"](new_channel), self.hass.loop
                ).result()

    def busDataReceived(self, busDataMessage: BusDataMessage) -> None:
        """Handle Haus-Bus messages."""

        object_id = ObjectId(busDataMessage.getSenderObjectId())
        data = busDataMessage.getData()
        deviceId = object_id.getDeviceId()
        templates = Templates.get_instance()

        # ignore messages sent from this module
        if deviceId in {HOMESERVER_DEVICE_ID, 9999, 12222}:
            return

        if deviceId in [
            110,
            503,
            1000,
            1541,
            3422,
            4000,
            4001,
            4002,
            4003,
            4004,
            4005,
            4009,
            4096,
            5068,
            8192,
            8270,
            11581,
            12223,
            12622,
            13976,
            14896,
            18343,
            19075,
            20043,
            21336,
            22909,
            24261,
            25661,
            25874,
            28900,
            3423,
            4006,
            4008,
        ]:
            return

        LOGGER.debug("busDataReceived with data = %s from %s", data, object_id)

        controller = Controller(object_id.getValue())

        # ModuleId -> getConfiguration
        if isinstance(data, ModuleId):
            LOGGER.debug("got moduleId of %s with data: %s", object_id.getDeviceId(), data)
            self.add_device(str(object_id.getDeviceId()), data)
            controller.getConfiguration()
            return

        # Bei unbekanntem Gerät -> ModuleId abfragen
        device = self.get_device(object_id)
        if device is None:
            LOGGER.debug(
                "got event of unknown device %s with data: %s", object_id.getDeviceId(), data
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

                # Spezialmodule
                if device.is_special_type():
                    update_needed = False
                    if device.is_leistungs_regler():
                        update_needed = device.set_model_id("SSR Leistungsregler")
                    elif device.is_rollo_modul():
                        nr_schalter = sum(
                            1
                            for instance in instances
                            if isinstance(instance, Schalter)
                        )
                        if nr_schalter > 6:
                            update_needed = device.set_model_id("8-fach Rollos")
                        else:
                            update_needed = device.set_model_id("2-fach Rollos")

                    if update_needed:
                        asyncio.run_coroutine_threadsafe(
                            self.async_update_device_registry(device), self.hass.loop
                        ).result()

                # Inputs merken für die Trigger
                inputs = []
                for instance in instances:
                    instanceObjectId = ObjectId(instance.getObjectId())
                    name = templates.get_feature_name_from_template(
                        device.firmware_id,
                        device.fcke,
                        instanceObjectId.getClassId(),
                        instanceObjectId.getInstanceId(),
                    )

                    LOGGER.debug(
                        "name for firmwareId %s, fcke: %s, classId %s, instanceId %s is %s", device.firmware_id, device.fcke, instanceObjectId.getClassId(), instanceObjectId.getInstanceId(), name
                    )

                    if deviceId in (HOMESERVER_DEVICE_ID, 9999, 12222):
                        className = ProxyFactory.getBusClassNameForClass(
                            instanceObjectId.getClassId()
                        ).rsplit(".", 1)[-1]
                        name = f"{className} {instanceObjectId.getInstanceId()}"
                        LOGGER.debug("specialName %s", name)

                    # automatische Namen für dynamische Elemente, die nicht alle in den Template stehen sollen
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

                        # Bei allen Taster Instanzen die Events anlegen, weil da auch ein Taster angeschlossen sein kann
                        if isinstance(instance, Taster):
                            inputs.append(name)

                if inputs:
                    self.hass.data.setdefault(DOMAIN, {})
                    self.hass.data[DOMAIN][device.hass_device_entry_id] = {
                        "inputs": inputs
                    }
                    LOGGER.debug(
                        "%s inputs angemeldet %s deviceId %s", inputs, device.hass_device_entry_id, deviceId
                    )

                return

        # Device_trigger und Events melden
        eventEntity = self.get_event_entity(object_id.getValue())
        if eventEntity is not None:
            LOGGER.debug("eventEntity is %s", eventEntity)
            eventEntity.handle_event(data)
            self.generate_device_trigger(data, device, object_id)

        # Alles andere wird an die jeweiligen Channel weitergeleitet
        channel = self.get_channel(object_id)

        # all channel events
        if isinstance(channel, HausbusEntity):
            LOGGER.debug("handle_event %s %s", channel, data)
            channel.handle_event(data)

        if isinstance(channel, HausbusRfidSensor) and isinstance(data, RfidEvData):
            LOGGER.debug("rfid data %s %s", channel, data)
            self.hass.loop.call_soon_threadsafe(
                lambda: self.hass.bus.async_fire(
                    "hausbus_rfid_event",
                    {"device_id": device.hass_device_entry_id, "tag": data.getTagID()},
                )
            )

        else:
            LOGGER.debug("kein zugehöriger channel")

    def generate_device_trigger(self, data, device: HausbusDevice, object_id: ObjectId):
        """Generates device trigger from a haus-bus event."""

        eventType = {
            EvCovered: "button_pressed",
            EvFree: "button_released",
            EvHoldStart: "button_hold_start",
            EvHoldEnd: "button_hold_end",
            EvClicked: "button_clicked",
            EvDoubleClick: "button_double_clicked",
        }.get(type(data), "unknown")

        if eventType != "unknown":
            name = Templates.get_instance().get_feature_name_from_template(
                device.firmware_id,
                device.fcke,
                object_id.getClassId(),
                object_id.getInstanceId(),
            )
            if name is not None:
                LOGGER.debug(
                    "sending trigger %s name %s hass_device_id %s", eventType, name, device.hass_device_entry_id
                )
                self.hass.loop.call_soon_threadsafe(
                    lambda: self.hass.bus.async_fire(
                        "hausbus_button_event",
                        {
                            "device_id": device.hass_device_entry_id,
                            "type": eventType,
                            "subtype": name,
                        },
                    )
                )
            else:
                LOGGER.debug("unknown name for event %s", data)

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
        device_registry = dr.get(self.hass)
        device_entry = device_registry.async_update_device(
            device.hass_device_entry_id, name=device.name
        )
        LOGGER.debug("updated hassEntryId = %s", device_entry.id)

    async def async_create_device_registry(self, device: HausbusDevice):
        """Creates a device in the hass registry."""
        device_registry = dr.get(self.hass)
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
                "no automatic get_module_id to %s because done before %.1f s", device_id, now - last_time
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
            LOGGER.debug("passt nicht %s", hausBusDevice.hass_device_entry_id)
        return False
