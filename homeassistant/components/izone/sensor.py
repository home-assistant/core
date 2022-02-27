"""Power sensor integration."""
from __future__ import annotations

import logging

from pizone.power import BatteryLevel, PowerChannel, PowerDevice, PowerGroup

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_POWER,
    PERCENTAGE,
    POWER_WATT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_DISCOVERY_SERVICE, DISPATCH_POWER_UPDATE
from .discovery import ControllerCoordinatorEntity, ControllerUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

_BATT_LEVEL_TO_PERCENT = {
    BatteryLevel.CRITICAL: 5,
    BatteryLevel.LOW: 30,
    BatteryLevel.NORMAL: 65,
    BatteryLevel.FULL: 100,
}


async def async_setup_entry(
    hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Initialize an IZone Controller."""
    disco = hass.data[DATA_DISCOVERY_SERVICE]

    @callback
    def init_controller(coordinator: ControllerUpdateCoordinator):
        """Register the controller device and the containing zones."""
        ctrl = coordinator.controller
        if not (ctrl.power and ctrl.power.enabled):
            _LOGGER.info(
                "Controller UID=%s ignored as doesn't support power", ctrl.device_uid
            )

        if not ctrl.power.groups:
            _LOGGER.info(
                "Controller UID=%s ignored as doesn't have any power groups",
                ctrl.device_uid,
            )

        _LOGGER.info("Controller UID=%s power monitoring discovered", ctrl.device_uid)

        async_add_entities(
            [SensorPowerGroup(coordinator, group) for group in ctrl.power.groups]
        )
        async_add_entities(
            [
                SensorDeviceBattery(coordinator, device)
                for device in ctrl.power.devices
                if device.enabled
            ]
        )
        async_add_entities(
            [
                SensorPowerChannel(coordinator, channel)
                for device in ctrl.power.devices
                for channel in device.channels
                if device.enabled and channel.enabled
            ]
        )

    disco.async_add_controller_discovered_listener(init_controller)


class SensorPowerChannel(ControllerCoordinatorEntity, SensorEntity):
    """Representation of a Power sensor channel."""

    def __init__(
        self, coordinator: ControllerUpdateCoordinator, channel: PowerChannel
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._channel = channel
        self._device_channel = (
            f"{self._channel.device.index + 1}-{chr(ord('A')+self._channel.index)}"
        )
        uid = f"{coordinator.controller.device_uid}_pc{self._device_channel}"
        self._attr_unique_id = uid
        self.entity_description = SensorEntityDescription(
            key=uid,
            device_class=DEVICE_CLASS_POWER,
            native_unit_of_measurement=POWER_WATT,
        )
        self._attr_device_info = coordinator.device_info
        self._attr_entity_registry_enabled_default = channel.group_number is None

    async def async_added_to_hass(self):
        """Call on adding to hass."""
        await super().async_added_to_hass()
        self.add_dispatcher_update(DISPATCH_POWER_UPDATE, self.controller)

    @property
    def name(self) -> str:
        """Return power channel name."""
        return f"Power Channel {self._channel.name}"

    @property
    def available(self) -> bool:
        """Return true if available."""
        return super().available and self._channel.device.status_ok

    @property
    def native_value(self) -> int:
        """Return power value."""
        return self._channel.status_power

    @property
    def extra_state_attributes(self):
        """Return the optional state attributes."""
        return {
            "generate": self._channel.generate,
            "add_to_total": self._channel.add_to_total,
            "device_channel": self._device_channel,
        }


class SensorPowerGroup(ControllerCoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    def __init__(
        self, coordinator: ControllerUpdateCoordinator, group: PowerGroup
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._group = group
        uid = f"{coordinator.controller.device_uid}_pg{group.group_number + 1}"
        self._attr_unique_id = uid
        self.entity_description = SensorEntityDescription(
            key=uid,
            device_class=DEVICE_CLASS_POWER,
            native_unit_of_measurement=POWER_WATT,
        )
        self._attr_device_info = coordinator.device_info

    async def async_added_to_hass(self):
        """Call on adding to hass."""
        await super().async_added_to_hass()
        self.add_dispatcher_update(DISPATCH_POWER_UPDATE, self.controller)

    @property
    def available(self) -> bool:
        """Return true if available."""
        return super().available and self._group.status_power

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Power Group " + self._group.name

    @property
    def native_value(self) -> int:
        """Return power value."""
        return self._group.status_power


class SensorDeviceBattery(ControllerCoordinatorEntity, SensorEntity):
    """Representation of a device's battery level."""

    def __init__(
        self, coordinator: ControllerUpdateCoordinator, device: PowerDevice
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device = device
        self._attr_name = f"Power Sensor {device.index} Battery Level"
        uid = f"{coordinator.controller.device_uid}_pdb{device.index + 1}"
        self._attr_unique_id = uid
        self.entity_description = SensorEntityDescription(
            key=uid,
            device_class=DEVICE_CLASS_BATTERY,
            native_unit_of_measurement=PERCENTAGE,
            entity_category=EntityCategory.DIAGNOSTIC,
        )
        self._attr_device_info = coordinator.device_info

    async def async_added_to_hass(self):
        """Call on adding to hass."""
        await super().async_added_to_hass()
        self.add_dispatcher_update(DISPATCH_POWER_UPDATE, self.controller)

    @property
    def available(self) -> bool:
        """Return true if available."""
        return super().available and self._device.status_ok

    @property
    def native_value(self) -> int:
        """Return power value."""
        return _BATT_LEVEL_TO_PERCENT[self._device.status_batt]

    @property
    def extra_state_attributes(self):
        """Return the optional state attributes."""
        return {"battery_text": self._device.status_batt.name.title()}
