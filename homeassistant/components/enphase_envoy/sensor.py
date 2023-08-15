"""Support for Enphase Envoy solar energy monitor."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import datetime
import logging

from pyenphase import (
    EnvoyEncharge,
    EnvoyEnchargeAggregate,
    EnvoyEnchargePower,
    EnvoyEnpower,
    EnvoyInverter,
    EnvoySystemConsumption,
    EnvoySystemProduction,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfApparentPower,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import EnphaseUpdateCoordinator
from .entity import EnvoyBaseEntity

ICON = "mdi:flash"
_LOGGER = logging.getLogger(__name__)

INVERTERS_KEY = "inverters"
LAST_REPORTED_KEY = "last_reported"


@dataclass
class EnvoyInverterRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[EnvoyInverter], datetime.datetime | float]


@dataclass
class EnvoyInverterSensorEntityDescription(
    SensorEntityDescription, EnvoyInverterRequiredKeysMixin
):
    """Describes an Envoy inverter sensor entity."""


INVERTER_SENSORS = (
    EnvoyInverterSensorEntityDescription(
        key=INVERTERS_KEY,
        name=None,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda inverter: inverter.last_report_watts,
    ),
    EnvoyInverterSensorEntityDescription(
        key=LAST_REPORTED_KEY,
        translation_key=LAST_REPORTED_KEY,
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        value_fn=lambda inverter: dt_util.utc_from_timestamp(inverter.last_report_date),
    ),
)


@dataclass
class EnvoyProductionRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[EnvoySystemProduction], int]


@dataclass
class EnvoyProductionSensorEntityDescription(
    SensorEntityDescription, EnvoyProductionRequiredKeysMixin
):
    """Describes an Envoy production sensor entity."""


PRODUCTION_SENSORS = (
    EnvoyProductionSensorEntityDescription(
        key="production",
        translation_key="current_power_production",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        suggested_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=3,
        value_fn=lambda production: production.watts_now,
    ),
    EnvoyProductionSensorEntityDescription(
        key="daily_production",
        translation_key="daily_production",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value_fn=lambda production: production.watt_hours_today,
    ),
    EnvoyProductionSensorEntityDescription(
        key="seven_days_production",
        translation_key="seven_days_production",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value_fn=lambda production: production.watt_hours_last_7_days,
    ),
    EnvoyProductionSensorEntityDescription(
        key="lifetime_production",
        translation_key="lifetime_production",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.MEGA_WATT_HOUR,
        suggested_display_precision=3,
        value_fn=lambda production: production.watt_hours_lifetime,
    ),
)


@dataclass
class EnvoyConsumptionRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[EnvoySystemConsumption], int]


@dataclass
class EnvoyConsumptionSensorEntityDescription(
    SensorEntityDescription, EnvoyConsumptionRequiredKeysMixin
):
    """Describes an Envoy consumption sensor entity."""


CONSUMPTION_SENSORS = (
    EnvoyConsumptionSensorEntityDescription(
        key="consumption",
        translation_key="current_power_consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        suggested_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=3,
        value_fn=lambda consumption: consumption.watts_now,
    ),
    EnvoyConsumptionSensorEntityDescription(
        key="daily_consumption",
        translation_key="daily_consumption",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value_fn=lambda consumption: consumption.watt_hours_today,
    ),
    EnvoyConsumptionSensorEntityDescription(
        key="seven_days_consumption",
        translation_key="seven_days_consumption",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value_fn=lambda consumption: consumption.watt_hours_last_7_days,
    ),
    EnvoyConsumptionSensorEntityDescription(
        key="lifetime_consumption",
        translation_key="lifetime_consumption",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        suggested_unit_of_measurement=UnitOfEnergy.MEGA_WATT_HOUR,
        suggested_display_precision=3,
        value_fn=lambda consumption: consumption.watt_hours_lifetime,
    ),
)


@dataclass
class EnvoyEnchargeRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[EnvoyEncharge], datetime.datetime | int | float]


@dataclass
class EnvoyEnchargeSensorEntityDescription(
    SensorEntityDescription, EnvoyEnchargeRequiredKeysMixin
):
    """Describes an Envoy Encharge sensor entity."""


@dataclass
class EnvoyEnchargePowerRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[EnvoyEnchargePower], int | float]


@dataclass
class EnvoyEnchargePowerSensorEntityDescription(
    SensorEntityDescription, EnvoyEnchargePowerRequiredKeysMixin
):
    """Describes an Envoy Encharge sensor entity."""


ENCHARGE_INVENTORY_SENSORS = (
    EnvoyEnchargeSensorEntityDescription(
        key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        value_fn=lambda encharge: encharge.temperature,
    ),
    EnvoyEnchargeSensorEntityDescription(
        key=LAST_REPORTED_KEY,
        translation_key=LAST_REPORTED_KEY,
        native_unit_of_measurement=None,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda encharge: dt_util.utc_from_timestamp(encharge.last_report_date),
    ),
)
ENCHARGE_POWER_SENSORS = (
    EnvoyEnchargePowerSensorEntityDescription(
        key="soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        value_fn=lambda encharge: encharge.soc,
    ),
    EnvoyEnchargePowerSensorEntityDescription(
        key="apparent_power_mva",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        value_fn=lambda encharge: encharge.apparent_power_mva * 0.001,
    ),
    EnvoyEnchargePowerSensorEntityDescription(
        key="real_power_mw",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda encharge: encharge.real_power_mw * 0.001,
    ),
)


@dataclass
class EnvoyEnpowerRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[EnvoyEnpower], datetime.datetime | int | float]


@dataclass
class EnvoyEnpowerSensorEntityDescription(
    SensorEntityDescription, EnvoyEnpowerRequiredKeysMixin
):
    """Describes an Envoy Encharge sensor entity."""


ENPOWER_SENSORS = (
    EnvoyEnpowerSensorEntityDescription(
        key="temperature",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        value_fn=lambda enpower: enpower.temperature,
    ),
    EnvoyEnpowerSensorEntityDescription(
        key=LAST_REPORTED_KEY,
        translation_key=LAST_REPORTED_KEY,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda enpower: dt_util.utc_from_timestamp(enpower.last_report_date),
    ),
)


@dataclass
class EnvoyEnchargeAggregateRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[EnvoyEnchargeAggregate], int]


@dataclass
class EnvoyEnchargeAggregateSensorEntityDescription(
    SensorEntityDescription, EnvoyEnchargeAggregateRequiredKeysMixin
):
    """Describes an Envoy Encharge sensor entity."""


ENCHARGE_AGGREGATE_SENSORS = (
    EnvoyEnchargeAggregateSensorEntityDescription(
        key="battery_level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        value_fn=lambda encharge: encharge.state_of_charge,
    ),
    EnvoyEnchargeAggregateSensorEntityDescription(
        key="reserve_soc",
        translation_key="reserve_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        value_fn=lambda encharge: encharge.reserve_state_of_charge,
    ),
    EnvoyEnchargeAggregateSensorEntityDescription(
        key="available_energy",
        translation_key="available_energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda encharge: encharge.available_energy,
    ),
    EnvoyEnchargeAggregateSensorEntityDescription(
        key="reserve_energy",
        translation_key="reserve_energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda encharge: encharge.backup_reserve,
    ),
    EnvoyEnchargeAggregateSensorEntityDescription(
        key="max_capacity",
        translation_key="max_capacity",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda encharge: encharge.max_available_capacity,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up envoy sensor platform."""
    coordinator: EnphaseUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    envoy_data = coordinator.envoy.data
    assert envoy_data is not None
    envoy_serial_num = config_entry.unique_id
    assert envoy_serial_num is not None
    _LOGGER.debug("Envoy data: %s", envoy_data)

    entities: list[Entity] = [
        EnvoyProductionEntity(coordinator, description)
        for description in PRODUCTION_SENSORS
    ]
    if envoy_data.system_consumption:
        entities.extend(
            EnvoyConsumptionEntity(coordinator, description)
            for description in CONSUMPTION_SENSORS
        )
    if envoy_data.inverters:
        entities.extend(
            EnvoyInverterEntity(coordinator, description, inverter)
            for description in INVERTER_SENSORS
            for inverter in envoy_data.inverters
        )

    if envoy_data.encharge_inventory:
        entities.extend(
            EnvoyEnchargeInventoryEntity(coordinator, description, encharge)
            for description in ENCHARGE_INVENTORY_SENSORS
            for encharge in envoy_data.encharge_inventory
        )
    if envoy_data.encharge_power:
        entities.extend(
            EnvoyEnchargePowerEntity(coordinator, description, encharge)
            for description in ENCHARGE_POWER_SENSORS
            for encharge in envoy_data.encharge_power
        )
    if envoy_data.encharge_aggregate:
        entities.extend(
            EnvoyEnchargeAggregateEntity(coordinator, description)
            for description in ENCHARGE_AGGREGATE_SENSORS
        )
    if envoy_data.enpower:
        entities.extend(
            EnvoyEnpowerEntity(coordinator, description)
            for description in ENPOWER_SENSORS
        )

    async_add_entities(entities)


class EnvoySensorBaseEntity(EnvoyBaseEntity, SensorEntity):
    """Defines a base envoy entity."""


class EnvoySystemSensorEntity(EnvoySensorBaseEntity):
    """Envoy system base entity."""

    _attr_icon = ICON

    def __init__(
        self,
        coordinator: EnphaseUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize Envoy entity."""
        super().__init__(coordinator, description)
        self._attr_unique_id = f"{self.envoy_serial_num}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.envoy_serial_num)},
            manufacturer="Enphase",
            model=coordinator.envoy.part_number or "Envoy",
            name=coordinator.name,
            sw_version=str(coordinator.envoy.firmware),
        )


class EnvoyProductionEntity(EnvoySystemSensorEntity):
    """Envoy production entity."""

    entity_description: EnvoyProductionSensorEntityDescription

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        system_production = self.data.system_production
        assert system_production is not None
        return self.entity_description.value_fn(system_production)


class EnvoyConsumptionEntity(EnvoySystemSensorEntity):
    """Envoy consumption entity."""

    entity_description: EnvoyConsumptionSensorEntityDescription

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        system_consumption = self.data.system_consumption
        assert system_consumption is not None
        return self.entity_description.value_fn(system_consumption)


class EnvoyInverterEntity(EnvoySensorBaseEntity):
    """Envoy inverter entity."""

    _attr_icon = ICON
    entity_description: EnvoyInverterSensorEntityDescription

    def __init__(
        self,
        coordinator: EnphaseUpdateCoordinator,
        description: EnvoyInverterSensorEntityDescription,
        serial_number: str,
    ) -> None:
        """Initialize Envoy inverter entity."""
        super().__init__(coordinator, description)
        self._serial_number = serial_number
        key = description.key
        if key == INVERTERS_KEY:
            # Originally there was only one inverter sensor, so we don't want to
            # break existing installations by changing the unique_id.
            self._attr_unique_id = serial_number
        else:
            # Additional sensors have a unique_id that includes the
            # sensor key.
            self._attr_unique_id = f"{serial_number}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            name=f"Inverter {serial_number}",
            manufacturer="Enphase",
            model="Inverter",
            via_device=(DOMAIN, self.envoy_serial_num),
        )

    @property
    def native_value(self) -> datetime.datetime | float:
        """Return the state of the sensor."""
        inverters = self.data.inverters
        assert inverters is not None
        return self.entity_description.value_fn(inverters[self._serial_number])


class EnvoyEnchargeEntity(EnvoySensorBaseEntity):
    """Envoy Encharge sensor entity."""

    def __init__(
        self,
        coordinator: EnphaseUpdateCoordinator,
        description: EnvoyEnchargeSensorEntityDescription
        | EnvoyEnchargePowerSensorEntityDescription,
        serial_number: str,
    ) -> None:
        """Initialize Encharge entity."""
        super().__init__(coordinator, description)
        self._serial_number = serial_number
        self._attr_unique_id = f"{serial_number}_{description.key}"
        encharge_inventory = self.data.encharge_inventory
        assert encharge_inventory is not None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            manufacturer="Enphase",
            model="Encharge",
            name=f"Encharge {serial_number}",
            sw_version=str(encharge_inventory[self._serial_number].firmware_version),
            via_device=(DOMAIN, self.envoy_serial_num),
        )


class EnvoyEnchargeInventoryEntity(EnvoyEnchargeEntity):
    """Envoy Encharge inventory entity."""

    entity_description: EnvoyEnchargeSensorEntityDescription

    @property
    def native_value(self) -> int | float | datetime.datetime | None:
        """Return the state of the inventory sensors."""
        encharge_inventory = self.data.encharge_inventory
        assert encharge_inventory is not None
        return self.entity_description.value_fn(encharge_inventory[self._serial_number])


class EnvoyEnchargePowerEntity(EnvoyEnchargeEntity):
    """Envoy Encharge power entity."""

    entity_description: EnvoyEnchargePowerSensorEntityDescription

    @property
    def native_value(self) -> int | float | None:
        """Return the state of the power sensors."""
        encharge_power = self.data.encharge_power
        assert encharge_power is not None
        return self.entity_description.value_fn(encharge_power[self._serial_number])


class EnvoyEnchargeAggregateEntity(EnvoySystemSensorEntity):
    """Envoy Encharge Aggregate sensor entity."""

    entity_description: EnvoyEnchargeAggregateSensorEntityDescription

    @property
    def native_value(self) -> int:
        """Return the state of the aggregate sensors."""
        encharge_aggregate = self.data.encharge_aggregate
        assert encharge_aggregate is not None
        return self.entity_description.value_fn(encharge_aggregate)


class EnvoyEnpowerEntity(EnvoySensorBaseEntity):
    """Envoy Enpower sensor entity."""

    entity_description: EnvoyEnpowerSensorEntityDescription

    def __init__(
        self,
        coordinator: EnphaseUpdateCoordinator,
        description: EnvoyEnpowerSensorEntityDescription,
    ) -> None:
        """Initialize Enpower entity."""
        super().__init__(coordinator, description)
        enpower_data = self.data.enpower
        assert enpower_data is not None
        self._attr_unique_id = f"{enpower_data.serial_number}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, enpower_data.serial_number)},
            manufacturer="Enphase",
            model="Enpower",
            name=f"Enpower {enpower_data.serial_number}",
            sw_version=str(enpower_data.firmware_version),
            via_device=(DOMAIN, self.envoy_serial_num),
        )

    @property
    def native_value(self) -> datetime.datetime | int | float | None:
        """Return the state of the power sensors."""
        enpower = self.data.enpower
        assert enpower is not None
        return self.entity_description.value_fn(enpower)
