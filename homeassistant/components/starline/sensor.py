"""Reads vehicle status from StarLine API."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ELECTRIC_POTENTIAL_VOLT,
    LENGTH_KILOMETERS,
    PERCENTAGE,
    TEMP_CELSIUS,
    VOLUME_LITERS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.icon import icon_for_battery_level, icon_for_signal_level

from .account import StarlineAccount, StarlineDevice
from .const import DOMAIN
from .entity import StarlineEntity


@dataclass
class StarlineRequiredKeysMixin:
    """Mixin for required keys."""

    name_: str


@dataclass
class StarlineSensorEntityDescription(
    SensorEntityDescription, StarlineRequiredKeysMixin
):
    """Describes Starline binary_sensor entity."""


SENSOR_TYPES: tuple[StarlineSensorEntityDescription, ...] = (
    StarlineSensorEntityDescription(
        key="battery",
        name_="Battery",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
    ),
    StarlineSensorEntityDescription(
        key="balance",
        name_="Balance",
        icon="mdi:cash-multiple",
    ),
    StarlineSensorEntityDescription(
        key="ctemp",
        name_="Interior Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    StarlineSensorEntityDescription(
        key="etemp",
        name_="Engine Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    StarlineSensorEntityDescription(
        key="gsm_lvl",
        name_="GSM Signal",
        native_unit_of_measurement=PERCENTAGE,
    ),
    StarlineSensorEntityDescription(
        key="fuel",
        name_="Fuel Volume",
        icon="mdi:fuel",
    ),
    StarlineSensorEntityDescription(
        key="errors",
        name_="OBD Errors",
        icon="mdi:alert-octagon",
    ),
    StarlineSensorEntityDescription(
        key="mileage",
        name_="Mileage",
        native_unit_of_measurement=LENGTH_KILOMETERS,
        icon="mdi:counter",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
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

    entity_description: StarlineSensorEntityDescription

    def __init__(
        self,
        account: StarlineAccount,
        device: StarlineDevice,
        description: StarlineSensorEntityDescription,
    ) -> None:
        """Initialize StarLine sensor."""
        super().__init__(account, device, description.key, description.name_)
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
                return VOLUME_LITERS
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
