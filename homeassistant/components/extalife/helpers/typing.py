from typing import TYPE_CHECKING

DeviceType = "Device"
DeviceManagerType = "DeviceManager"
TransmitterManagerType = "TransmitterManager"
ChannelDataManagerType = "ChannelDataManager"
CoreType = "Core"  # "Core"
ExtaLifeTransmitterEventProcessorType = "ExtaLifeTransmitterEventProcessor"


if TYPE_CHECKING:
    from .. import ChannelDataManager
    from ..transmitter import TransmitterManager
    from .core import Core
    from .device import Device, DeviceManager, ExtaLifeTransmitterEventProcessor

    DeviceType = Device
    DeviceManagerType = DeviceManager
    TransmitterManagerType = TransmitterManager
    ChannelDataManagerType = ChannelDataManager
    CoreType = Core
    ExtaLifeTransmitterEventProcessorType = ExtaLifeTransmitterEventProcessor
