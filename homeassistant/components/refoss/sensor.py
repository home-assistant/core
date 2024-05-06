"""Support for refoss sensors."""

from __future__ import annotations

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
    DEVICE_CLASS_UNITS,
    DISPATCH_DEVICE_DISCOVERED,
    DOMAIN,
    ENERGY,
    ENERGY_RETURNED,
    UnitOfEnergy,
    UnitOfMeasurement,
)
from .entity import RefossEntity


@dataclass(frozen=True)
class RefossSensorEntityDescription(SensorEntityDescription):
    """Describes Refoss sensor entity."""

    subkey: str | None = None


SENSORS: dict[str, tuple[RefossSensorEntityDescription, ...]] = {
    "em06": (
        RefossSensorEntityDescription(
            key="power",
            name="Power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.WATT,
            subkey="power",
        ),
        RefossSensorEntityDescription(
            key="voltage",
            name="Voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            subkey="voltage",
        ),
        RefossSensorEntityDescription(
            key="current",
            name="Current",
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            subkey="current",
        ),
        RefossSensorEntityDescription(
            key="factor",
            name="Power Factor",
            device_class=SensorDeviceClass.POWER_FACTOR,
            state_class=SensorStateClass.MEASUREMENT,
            subkey="factor",
        ),
        RefossSensorEntityDescription(
            key="energy",
            name="This Month Energy",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            subkey="mConsume",
        ),
        RefossSensorEntityDescription(
            key="energy_returned",
            name="This Month Energy Returned",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            subkey="mConsume",
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
    _uom: UnitOfMeasurement | None = None
    _channel_status: None

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

        if self.device_class is not None:
            if (
                self.native_unit_of_measurement is None
                or self.device_class not in DEVICE_CLASS_UNITS
            ):
                self._attr_device_class = None
                return

            uoms = DEVICE_CLASS_UNITS[self.device_class]
            self._uom = uoms.get(self.native_unit_of_measurement) or uoms.get(
                self.native_unit_of_measurement.lower()
            )
            if self._uom is None:
                self._attr_device_class = None
                return
            self._attr_native_unit_of_measurement = (
                self._uom.conversion_unit or self._uom.unit
            )

    @property
    def native_value(self) -> StateType:
        """Return the native value."""
        self._channel_status = self.coordinator.device.status.get(self.channel_id)
        if self._channel_status is None:
            return None

        value = self._channel_status.get(self.entity_description.subkey)
        if value is None:
            return None
        if self.entity_description.key == ENERGY and value < 0:
            return 0

        if self.entity_description.key == ENERGY_RETURNED and value > 0:
            return 0

        if self._uom and self._uom.conversion_fn is not None:
            return self._uom.conversion_fn(value)

        if isinstance(value, float):
            return round(value, 2)
        return value
