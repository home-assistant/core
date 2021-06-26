"""Switcher integration Sensor platform."""
from __future__ import annotations

from dataclasses import dataclass

from aioswitcher.consts import WAITING_TEXT
from aioswitcher.devices import SwitcherV2Device

from homeassistant.components.sensor import (
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_POWER,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)
from homeassistant.const import ELECTRICAL_CURRENT_AMPERE, POWER_WATT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType, StateType

from .const import DATA_DEVICE, DOMAIN, SIGNAL_SWITCHER_DEVICE_UPDATE


@dataclass
class AttributeDescription:
    """Class to describe a sensor."""

    name: str
    icon: str | None = None
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    default_enabled: bool = True
    default_value: float | int | str | None = None


POWER_SENSORS = {
    "power_consumption": AttributeDescription(
        name="Power Consumption",
        unit=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
        default_value=0,
    ),
    "electric_current": AttributeDescription(
        name="Electric Current",
        unit=ELECTRICAL_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        state_class=STATE_CLASS_MEASUREMENT,
        default_value=0.0,
    ),
}

TIME_SENSORS = {
    "remaining_time": AttributeDescription(
        name="Remaining Time",
        icon="mdi:av-timer",
        default_value="00:00:00",
    ),
    "auto_off_set": AttributeDescription(
        name="Auto Shutdown",
        icon="mdi:progress-clock",
        default_enabled=False,
        default_value="00:00:00",
    ),
}

SENSORS = {**POWER_SENSORS, **TIME_SENSORS}


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType,
) -> None:
    """Set up Switcher sensor from config entry."""
    device_data = hass.data[DOMAIN][DATA_DEVICE]

    async_add_entities(
        SwitcherSensorEntity(device_data, attribute, SENSORS[attribute])
        for attribute in SENSORS
    )


class SwitcherSensorEntity(SensorEntity):
    """Representation of a Switcher sensor entity."""

    def __init__(
        self,
        device_data: SwitcherV2Device,
        attribute: str,
        description: AttributeDescription,
    ) -> None:
        """Initialize the entity."""
        self._device_data = device_data
        self.attribute = attribute
        self.description = description

        # Entity class attributes
        self._attr_name = f"{self._device_data.name} {self.description.name}"
        self._attr_icon = self.description.icon
        self._attr_unit_of_measurement = self.description.unit
        self._attr_device_class = self.description.device_class
        self._attr_entity_registry_enabled_default = self.description.default_enabled
        self._attr_should_poll = False

        self._attr_unique_id = f"{self._device_data.device_id}-{self._device_data.mac_addr}-{self.attribute}"

    @property
    def state(self) -> StateType:
        """Return value of sensor."""
        value = getattr(self._device_data, self.attribute)
        if value and value is not WAITING_TEXT:
            return value

        return self.description.default_value

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_SWITCHER_DEVICE_UPDATE, self.async_update_data
            )
        )

    @callback
    def async_update_data(self, device_data: SwitcherV2Device) -> None:
        """Update the entity data."""
        self._device_data = device_data
        self.async_write_ha_state()
