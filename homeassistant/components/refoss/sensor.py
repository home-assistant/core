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
)
from .entity import RefossEntity


@dataclass(frozen=True, kw_only=True)
class RefossSensorEntityDescription(SensorEntityDescription):
    """Describes Refoss sensor entity."""

    subkey: str
    fn: Callable[[float], float] = lambda x: x


SENSORS: dict[str, tuple[RefossSensorEntityDescription, ...]] = {
    "em06": (
        RefossSensorEntityDescription(
            key="power",
            translation_key="power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.WATT,
            suggested_display_precision=2,
            subkey="power",
            fn=lambda x: x / 1000.0,
        ),
        RefossSensorEntityDescription(
            key="voltage",
            translation_key="voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
            suggested_display_precision=2,
            suggested_unit_of_measurement=UnitOfElectricPotential.VOLT,
            subkey="voltage",
        ),
        RefossSensorEntityDescription(
            key="current",
            translation_key="current",
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
            suggested_display_precision=2,
            suggested_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            subkey="current",
        ),
        RefossSensorEntityDescription(
            key="factor",
            translation_key="power_factor",
            device_class=SensorDeviceClass.POWER_FACTOR,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=2,
            subkey="factor",
        ),
        RefossSensorEntityDescription(
            key="energy",
            translation_key="this_month_energy",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            suggested_display_precision=2,
            subkey="mConsume",
            fn=lambda x: max(0, x),
        ),
        RefossSensorEntityDescription(
            key="energy_returned",
            translation_key="this_month_energy_returned",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            suggested_display_precision=2,
            subkey="mConsume",
            fn=lambda x: abs(x) if x < 0 else 0,
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
    def init_device(coordinator: RefossDataUpdateCoordinator) -> None:
        """Register the device."""
        device = coordinator.device

        if not isinstance(device, ElectricityXMix):
            return
        descriptions: tuple[RefossSensorEntityDescription, ...] = SENSORS.get(
            device.device_type, ()
        )

        async_add_entities(
            RefossSensor(
                coordinator=coordinator,
                channel=channel,
                description=description,
            )
            for channel in device.channels
            for description in descriptions
        )

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
        channel_name = CHANNEL_DISPLAY_NAME[device_type][channel]
        self._attr_translation_placeholders = {"channel_name": channel_name}

    @property
    def native_value(self) -> StateType:
        """Return the native value."""
        value = self.coordinator.device.get_value(
            self.channel_id, self.entity_description.subkey
        )
        if value is None:
            return None
        return self.entity_description.fn(value)
