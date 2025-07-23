"""Support for HomematicIP Cloud valve devices."""

from homematicip.base.functionalChannels import FunctionalChannelType
from homematicip.device import Device

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import HomematicipGenericEntity
from .hap import HomematicIPConfigEntry, HomematicipHAP


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomematicIPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the HomematicIP valves from a config entry."""
    hap = config_entry.runtime_data
    entities = [
        HomematicipWateringValve(hap, device, ch.index)
        for device in hap.home.devices
        for ch in device.functionalChannels
        if ch.functionalChannelType == FunctionalChannelType.WATERING_ACTUATOR_CHANNEL
    ]

    async_add_entities(entities)


class HomematicipWateringValve(HomematicipGenericEntity, ValveEntity):
    """Representation of a HomematicIP valve."""

    _attr_reports_position = False
    _attr_supported_features = ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
    _attr_device_class = ValveDeviceClass.WATER

    def __init__(self, hap: HomematicipHAP, device: Device, channel: int) -> None:
        """Initialize the valve."""
        super().__init__(
            hap, device=device, channel=channel, post="watering", is_multi_channel=True
        )

    async def async_open_valve(self) -> None:
        """Open the valve."""
        await self.functional_channel.set_watering_switch_state_async(True)

    async def async_close_valve(self) -> None:
        """Close valve."""
        await self.functional_channel.set_watering_switch_state_async(False)

    @property
    def is_closed(self) -> bool:
        """Return if the valve is closed."""
        return self.functional_channel.wateringActive is False
