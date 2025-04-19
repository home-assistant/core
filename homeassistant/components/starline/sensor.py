"""Reads vehicle status from StarLine API."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.icon import icon_for_battery_level, icon_for_signal_level

from .account import StarlineAccount, StarlineDevice
from .const import DOMAIN
from .entity import StarlineEntity

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="balance",
        translation_key="balance",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="ctemp",
        translation_key="interior_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="etemp",
        translation_key="engine_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="gsm_lvl",
        translation_key="gsm_signal",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="fuel",
        translation_key="fuel",
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="errors",
        translation_key="errors",
        native_unit_of_measurement="errors",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="mileage",
        translation_key="mileage",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="gps_count",
        translation_key="gps_count",
        native_unit_of_measurement="satellites",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the StarLine sensors."""
    account: StarlineAccount = hass.data[DOMAIN][entry.entry_id]
    entities = [
        sensor
        for device in account.api.devices.values()
        for description in SENSOR_TYPES
        if (sensor := StarlineSensor(account, device, description)).native_value
        is not None
    ]
    async_add_entities(entities)


class StarlineSensor(StarlineEntity, SensorEntity):
    """Representation of a StarLine sensor."""

    def __init__(
        self,
        account: StarlineAccount,
        device: StarlineDevice,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize StarLine sensor."""
        super().__init__(account, device, description.key)
        self.entity_description = description

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if self._key == "battery":
            return icon_for_battery_level(
                battery_level=self._device.battery_level_percent,
                charging=self._device.car_state.get("ign", False),
            )
        if self._key == "gsm_lvl":
            return icon_for_signal_level(signal_level=self._device.gsm_level_percent)
        return self.entity_description.icon

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self._key == "battery":
            return self._device.battery_level
        if self._key == "balance":
            return self._device.balance.get("value")
        if self._key == "ctemp":
            return self._device.temp_inner
        if self._key == "etemp":
            return self._device.temp_engine
        if self._key == "gsm_lvl":
            return self._device.gsm_level_percent
        if self._key == "fuel" and self._device.fuel:
            return self._device.fuel.get("val")
        if self._key == "errors" and self._device.errors:
            return self._device.errors.get("val")
        if self._key == "mileage" and self._device.mileage:
            return self._device.mileage.get("val")
        if self._key == "gps_count" and self._device.position:
            return self._device.position.get("sat_qty")
        return None

    @property
    def native_unit_of_measurement(self):
        """Get the unit of measurement."""
        if self._key == "balance":
            return self._device.balance.get("currency") or "₽"
        if self._key == "fuel":
            type_value = self._device.fuel.get("type")
            if type_value == "percents":
                return PERCENTAGE
            if type_value == "litres":
                return UnitOfVolume.LITERS
        return self.entity_description.native_unit_of_measurement

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        if self._key == "balance":
            return self._account.balance_attrs(self._device)
        if self._key == "gsm_lvl":
            return self._account.gsm_attrs(self._device)
        if self._key == "errors":
            return self._account.errors_attrs(self._device)
        return None
