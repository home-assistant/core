"""Support for SwitchBot Cloud binary sensors."""

from dataclasses import dataclass

from switchbot_api import Device, SwitchBotAPI

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SwitchbotCloudData
from .const import DOMAIN
from .coordinator import SwitchBotCoordinator
from .entity import SwitchBotCloudEntity


@dataclass(frozen=True)
class SwitchBotCloudBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Switchbot Cloud binary sensor."""

    # Value or values to consider binary sensor to be "on"
    on_value: bool | str = True


CALIBRATION_DESCRIPTION = SwitchBotCloudBinarySensorEntityDescription(
    key="calibrate",
    name="Calibration",
    translation_key="calibration",
    device_class=BinarySensorDeviceClass.PROBLEM,
    entity_category=EntityCategory.DIAGNOSTIC,
    on_value=False,
)

DOOR_OPEN_DESCRIPTION = SwitchBotCloudBinarySensorEntityDescription(
    key="doorState",
    device_class=BinarySensorDeviceClass.DOOR,
    on_value="opened",
)

BINARY_SENSOR_DESCRIPTIONS_BY_DEVICE_TYPES = {
    "Smart Lock": (
        CALIBRATION_DESCRIPTION,
        DOOR_OPEN_DESCRIPTION,
    ),
    "Smart Lock Pro": (
        CALIBRATION_DESCRIPTION,
        DOOR_OPEN_DESCRIPTION,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][config.entry_id]

    async_add_entities(
        SwitchBotCloudBinarySensor(data.api, device, coordinator, description)
        for device, coordinator in data.devices.binary_sensors
        for description in BINARY_SENSOR_DESCRIPTIONS_BY_DEVICE_TYPES[
            device.device_type
        ]
    )


class SwitchBotCloudBinarySensor(SwitchBotCloudEntity, BinarySensorEntity):
    """Representation of a Switchbot binary sensor."""

    entity_description: SwitchBotCloudBinarySensorEntityDescription

    def __init__(
        self,
        api: SwitchBotAPI,
        device: Device,
        coordinator: SwitchBotCoordinator,
        description: SwitchBotCloudBinarySensorEntityDescription,
    ) -> None:
        """Initialize SwitchBot Cloud sensor entity."""
        super().__init__(api, device, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{device.device_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Set attributes from coordinator data."""
        if not self.coordinator.data:
            return None

        return (
            self.coordinator.data.get(self.entity_description.key)
            == self.entity_description.on_value
        )
