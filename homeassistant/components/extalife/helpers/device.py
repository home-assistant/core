"""Provides device automations for Exta Life."""
import logging
from typing import List

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry,
)
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from ..pyextalife import (
    DEVICE_ARR_ALL_TRANSMITTER,
    MODEL_LEDIX_P260,
    MODEL_P501,
    MODEL_P520,
    MODEL_P521L,
    MODEL_P4572,
    MODEL_P4574,
    MODEL_P4578,
    MODEL_P45736,
    MODEL_RNK22,
    MODEL_RNK24,
    MODEL_RNM24,
    MODEL_RNP21,
    MODEL_RNP22,
)
from .const import (
    CONF_EXTALIFE_EVENT_TRANSMITTER,
    CONF_PROCESSOR_EVENT_STAT_NOTIFICATION,
    DOMAIN,
    TRIGGER_BUTTON_DOUBLE_CLICK,
    TRIGGER_BUTTON_DOWN,
    TRIGGER_BUTTON_LONG_PRESS,
    TRIGGER_BUTTON_SINGLE_CLICK,
    TRIGGER_BUTTON_TRIPLE_CLICK,
    TRIGGER_BUTTON_UP,
    TRIGGER_SUBTYPE,
    TRIGGER_SUBTYPE_BUTTON_TEMPLATE,
    TRIGGER_TYPE,
)
from .typing import ExtaLifeTransmitterEventProcessorType

_LOGGER = logging.getLogger(__name__)


class DeviceEvent:
    def __init__(self, event, unique_id):
        """
        event - event in HA
        unique_id - unique identifier of the event source e.g. unique device id
        """
        self._event = event
        self._unique_id = unique_id

    @property
    def event(self):
        return self._event

    @property
    def unique_id(self):
        return self._unique_id


class Device:
    def __init__(self, device: DeviceEntry, type):
        """dev_info - device info - the same passed to Device Registry
        type  - Exta Life module type e.g 10 = ROP-21"""
        self._type = type
        self._device = device
        self._event_processor = None

    @property
    def model(self):
        return self._device.model

    @property
    def type(self):
        return self._type

    @property
    def identifiers(self) -> set:
        return self._device.identifiers

    @property
    def unique_id(self):

        # unpack tuple from set and return unique_id by list generator and list index 0
        return [tuple for tuple in self.identifiers][0][1]

    @property
    def registry_id(self) -> str:
        return self._device.id

    @property
    def triggers(self) -> list:
        pass

    def controller_event(self, dataa):
        _LOGGER.debug("Device.controller_event")
        pass

    @property
    def config_entry_id(self):
        return [t for t in self._device.config_entries][
            0
        ]  # the same device can exist only in 1 Config Entry

    @property
    def event(self) -> DeviceEvent:
        return DeviceEvent(CONF_EXTALIFE_EVENT_TRANSMITTER, self.unique_id)


class DeviceFactory:
    @staticmethod
    def get_device(device: DeviceEntry, type) -> Device:  # subclass
        if type in DEVICE_ARR_ALL_TRANSMITTER:
            return TransmitterDevice(device, type)
        else:
            raise NotImplementedError


class TransmitterDevice(Device):
    def __init__(self, device: DeviceEntry, type):
        from .event import ExtaLifeTransmitterEventProcessor

        super().__init__(device, type)
        self._event_processor = ExtaLifeTransmitterEventProcessor(self)

    @property
    def triggers(self) -> list:
        triggers = []

        trigger_type = (
            TRIGGER_BUTTON_UP,
            TRIGGER_BUTTON_DOWN,
            TRIGGER_BUTTON_SINGLE_CLICK,
            TRIGGER_BUTTON_DOUBLE_CLICK,
            TRIGGER_BUTTON_TRIPLE_CLICK,
            TRIGGER_BUTTON_LONG_PRESS,
        )
        buttons = 0
        if self.model in (MODEL_RNK22, MODEL_P4572):
            buttons = 2
        elif self.model in (
            MODEL_RNK24,
            MODEL_P4574,
            MODEL_RNM24,
            MODEL_RNP21,
            MODEL_RNP22,
        ):
            buttons = 4
        elif self.model in (MODEL_P4578):
            buttons = 8
        elif self.model in (MODEL_P45736):
            buttons = 36

        for button in range(1, buttons + 1):
            for type in trigger_type:
                triggers.append(
                    {
                        TRIGGER_TYPE: type,
                        TRIGGER_SUBTYPE: TRIGGER_SUBTYPE_BUTTON_TEMPLATE.format(button),
                    }
                )

        return triggers

    def controller_event(self, data):
        _LOGGER.debug("TransmitterDevice.controller_event")
        super().controller_event(data)
        self._event_processor.process_event(
            data, event_type=CONF_PROCESSOR_EVENT_STAT_NOTIFICATION
        )


class DeviceManager:
    def __init__(self, config_entry: ConfigEntry, core: "Core"):
        from .core import Core

        self._core = core
        self._config_entry = config_entry

        self._devices = dict()

    async def register_in_dr(self, dev_info: dict) -> DeviceEntry:
        device_registry = await dr.async_get_registry(self._core.hass)

        device_entry = device_registry.async_get_or_create(
            config_entry_id=self._config_entry.entry_id, **dev_info
        )

        return device_entry

    async def async_add(self, type, dev_info=None, ha_device=None) -> Device:
        """
        dev_info - device info data in HA device registry format. To be passed to HA Device Registry
        type  - Exta Life module type e.g 10 = ROP-21
        ha_device: DeviceEntry - boolean whether to register device in HA Device Registry or not
        """

        device_entry = ha_device if ha_device else await self.register_in_dr(dev_info)
        device = DeviceFactory.get_device(device_entry, type)

        self._devices.update({device_entry.id: device})
        return device

    async def async_get_by_registry_id(self, device_id) -> Device:
        """ Get device by HA Device Registry id """
        return self._devices.get(device_id)
