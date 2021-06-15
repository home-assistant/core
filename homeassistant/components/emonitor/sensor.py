"""Support for a Emonitor channel sensor."""

from aioemonitor.monitor import EmonitorChannel

from homeassistant.components.sensor import DEVICE_CLASS_POWER, SensorEntity
from homeassistant.const import POWER_WATT
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import name_short_mac
from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    channels = coordinator.data.channels
    entities = []
    seen_channels = set()
    for channel_number, channel in channels.items():
        seen_channels.add(channel_number)
        if not channel.active:
            continue
        if channel.paired_with_channel in seen_channels:
            continue

        entities.append(EmonitorPowerSensor(coordinator, channel_number))

    async_add_entities(entities)


class EmonitorPowerSensor(CoordinatorEntity, SensorEntity):
    """Representation of an Emonitor power sensor entity."""

    _attr_device_class = DEVICE_CLASS_POWER
    _attr_unit_of_measurement = POWER_WATT

    def __init__(self, coordinator: DataUpdateCoordinator, channel_number: int) -> None:
        """Initialize the channel sensor."""
        self.channel_number = channel_number
        super().__init__(coordinator)

    @property
    def unique_id(self) -> str:
        """Channel unique id."""
        return f"{self.mac_address}_{self.channel_number}"

    @property
    def channel_data(self) -> EmonitorChannel:
        """Channel data."""
        return self.coordinator.data.channels[self.channel_number]

    @property
    def paired_channel_data(self) -> EmonitorChannel:
        """Channel data."""
        return self.coordinator.data.channels[self.channel_data.paired_with_channel]

    @property
    def name(self) -> str:
        """Name of the sensor."""
        return self.channel_data.label

    def _paired_attr(self, attr_name: str) -> float:
        """Cumulative attributes for channel and paired channel."""
        attr_val = getattr(self.channel_data, attr_name)
        if self.channel_data.paired_with_channel:
            attr_val += getattr(self.paired_channel_data, attr_name)
        return attr_val

    @property
    def state(self) -> StateType:
        """State of the sensor."""
        return self._paired_attr("inst_power")

    @property
    def extra_state_attributes(self) -> dict:
        """Return the device specific state attributes."""
        return {
            "channel": self.channel_number,
            "avg_power": self._paired_attr("avg_power"),
            "max_power": self._paired_attr("max_power"),
        }

    @property
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self.coordinator.data.network.mac_address

    @property
    def device_info(self) -> DeviceInfo:
        """Return info about the emonitor device."""
        return {
            "name": name_short_mac(self.mac_address[-6:]),
            "connections": {(dr.CONNECTION_NETWORK_MAC, self.mac_address)},
            "manufacturer": "Powerhouse Dynamics, Inc.",
            "sw_version": self.coordinator.data.hardware.firmware_version,
        }
