"""Support for refoss sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from refoss_ha.controller.electricity import ElectricityXMix

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .bridge import RefossDataUpdateCoordinator
from .const import (
    CHANNEL_DISPLAY_NAME,
    COORDINATORS,
    DISPATCH_DEVICE_DISCOVERED,
    DOMAIN,
    ENERGY,
    ENERGY_RETURNED,
)
from .entity import RefossEntity


@dataclass(frozen=True)
class RefossSensorEntityDescription(SensorEntityDescription):
    """Describes Refoss sensor entity."""

    subkey: str | None = None
    fn: Callable[[float], float] | None = None


SENSORS: dict[str, tuple[RefossSensorEntityDescription, ...]] = {
    "em06": (
        RefossSensorEntityDescription(
            key="power",
            name="Power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.WATT,
            subkey="power",
            fn=lambda x: round(x / 1000, 2),
        ),
        RefossSensorEntityDescription(
            key="voltage",
            name="Voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            subkey="voltage",
            fn=lambda x: round(x / 1000, 2),
        ),
        RefossSensorEntityDescription(
            key="current",
            name="Current",
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            subkey="current",
            fn=lambda x: round(x / 1000, 2),
        ),
        RefossSensorEntityDescription(
            key="factor",
            name="Power Factor",
            device_class=SensorDeviceClass.POWER_FACTOR,
            state_class=SensorStateClass.MEASUREMENT,
            subkey="factor",
            fn=lambda x: round(x, 2),
        ),
        RefossSensorEntityDescription(
            key="energy",
            name="This Month Energy",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            subkey="mConsume",
            fn=lambda x: round(x, 2),
        ),
        RefossSensorEntityDescription(
            key="energy_returned",
            name="This Month Energy Returned",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            subkey="mConsume",
            fn=lambda x: round(x, 2),
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Refoss device from a config entry."""

    @callback
    def init_device(coordinator):
        """Register the device."""
        device = coordinator.device

        if not isinstance(device, ElectricityXMix):
            return
        descriptions = SENSORS.get(device.device_type)
        new_entities = []
        for channel in device.channels:
            for description in descriptions:
                entity = RefossSensor(
                    coordinator=coordinator,
                    channel=channel,
                    description=description,
                )
                new_entities.append(entity)

        async_add_entities(new_entities)

    for coordinator in hass.data[DOMAIN][COORDINATORS]:
        init_device(coordinator)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, DISPATCH_DEVICE_DISCOVERED, init_device)
    )


class RefossSensor(RefossEntity, SensorEntity):
    """Refoss Sensor Device."""

    entity_description: RefossSensorEntityDescription

    def __init__(
        self,
        coordinator: RefossDataUpdateCoordinator,
        channel: int,
        description: RefossSensorEntityDescription,
    ) -> None:
        """Init Refoss sensor."""
        super().__init__(coordinator, channel)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"
        device_type = coordinator.device.device_type
        self._attr_name = (
            f"{CHANNEL_DISPLAY_NAME[device_type][channel]} {description.name}"
        )

    @property
    def native_value(self) -> StateType:
        """Return the native value."""
        value = self.coordinator.device.get_value(
            self.channel_id, self.entity_description.subkey
        )
        if value is None:
            return None
        if (self.entity_description.key == ENERGY and value < 0) or (
            self.entity_description.key == ENERGY_RETURNED and value > 0
        ):
            value = 0
        if self.entity_description.fn is not None:
            return self.entity_description.fn(value)
        return value
