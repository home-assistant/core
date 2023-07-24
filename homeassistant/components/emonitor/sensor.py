"""Support for a Emonitor channel sensor."""
from __future__ import annotations

from aioemonitor.monitor import EmonitorChannel, EmonitorStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import UNDEFINED, StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import name_short_mac
from .const import DOMAIN

SENSORS = (
    SensorEntityDescription(key="inst_power"),
    SensorEntityDescription(
        key="avg_power", name="Average", entity_registry_enabled_default=False
    ),
    SensorEntityDescription(
        key="max_power", name="Max", entity_registry_enabled_default=False
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    channels = coordinator.data.channels
    entities: list[EmonitorPowerSensor] = []
    seen_channels = set()
    for channel_number, channel in channels.items():
        seen_channels.add(channel_number)
        if not channel.active:
            continue
        if channel.paired_with_channel in seen_channels:
            continue

        entities.extend(
            EmonitorPowerSensor(coordinator, description, channel_number)
            for description in SENSORS
        )

    async_add_entities(entities)


class EmonitorPowerSensor(CoordinatorEntity, SensorEntity):
    """Representation of an Emonitor power sensor entity."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: SensorEntityDescription,
        channel_number: int,
    ) -> None:
        """Initialize the channel sensor."""
        self.entity_description = description
        self.channel_number = channel_number
        super().__init__(coordinator)
        mac_address = self.emonitor_status.network.mac_address
        device_name = name_short_mac(mac_address[-6:])
        label = self.channel_data.label or f"{device_name} {channel_number}"
        if description.name is not UNDEFINED:
            self._attr_name = f"{label} {description.name}"
            self._attr_unique_id = f"{mac_address}_{channel_number}_{description.key}"
        else:
            self._attr_name = label
            self._attr_unique_id = f"{mac_address}_{channel_number}"
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, mac_address)},
            manufacturer="Powerhouse Dynamics, Inc.",
            name=device_name,
            sw_version=self.emonitor_status.hardware.firmware_version,
        )

    @property
    def channels(self) -> dict[int, EmonitorChannel]:
        """Return the channels dict."""
        channels: dict[int, EmonitorChannel] = self.emonitor_status.channels
        return channels

    @property
    def channel_data(self) -> EmonitorChannel:
        """Return the channel data."""
        return self.channels[self.channel_number]

    @property
    def emonitor_status(self) -> EmonitorStatus:
        """Return the EmonitorStatus."""
        return self.coordinator.data

    def _paired_attr(self, attr_name: str) -> float:
        """Cumulative attributes for channel and paired channel."""
        channel_data = self.channels[self.channel_number]
        attr_val = getattr(channel_data, attr_name)
        if paired_channel := channel_data.paired_with_channel:
            attr_val += getattr(self.channels[paired_channel], attr_name)
        return attr_val

    @property
    def native_value(self) -> StateType:
        """State of the sensor."""
        return self._paired_attr(self.entity_description.key)

    @property
    def extra_state_attributes(self) -> dict[str, int]:
        """Return the device specific state attributes."""
        return {"channel": self.channel_number}
