"""Support for Enphase Envoy solar energy monitor."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import datetime
import logging

from pyenphase import EnvoyInverter, EnvoySystemConsumption, EnvoySystemProduction

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import EnphaseUpdateCoordinator

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

    async_add_entities(entities)


class EnvoyEntity(CoordinatorEntity[EnphaseUpdateCoordinator], SensorEntity):
    """Envoy inverter entity."""

    _attr_icon = ICON
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EnphaseUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize Envoy entity."""
        self.entity_description = description
        envoy_name = coordinator.name
        envoy_serial_num = coordinator.envoy.serial_number
        assert envoy_serial_num is not None
        self._attr_unique_id = f"{envoy_serial_num}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, envoy_serial_num)},
            manufacturer="Enphase",
            model=coordinator.envoy.part_number or "Envoy",
            name=envoy_name,
            sw_version=str(coordinator.envoy.firmware),
        )
        super().__init__(coordinator)


class EnvoyProductionEntity(EnvoyEntity):
    """Envoy production entity."""

    entity_description: EnvoyProductionSensorEntityDescription

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        envoy = self.coordinator.envoy
        assert envoy.data is not None
        assert envoy.data.system_production is not None
        return self.entity_description.value_fn(envoy.data.system_production)


class EnvoyConsumptionEntity(EnvoyEntity):
    """Envoy consumption entity."""

    entity_description: EnvoyConsumptionSensorEntityDescription

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        envoy = self.coordinator.envoy
        assert envoy.data is not None
        assert envoy.data.system_consumption is not None
        return self.entity_description.value_fn(envoy.data.system_consumption)


class EnvoyInverterEntity(CoordinatorEntity[EnphaseUpdateCoordinator], SensorEntity):
    """Envoy inverter entity."""

    _attr_icon = ICON
    _attr_has_entity_name = True
    entity_description: EnvoyInverterSensorEntityDescription

    def __init__(
        self,
        coordinator: EnphaseUpdateCoordinator,
        description: EnvoyInverterSensorEntityDescription,
        serial_number: str,
    ) -> None:
        """Initialize Envoy inverter entity."""
        self.entity_description = description
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

        envoy_serial_num = coordinator.envoy.serial_number
        assert envoy_serial_num is not None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            name=f"Inverter {serial_number}",
            manufacturer="Enphase",
            model="Inverter",
            via_device=(DOMAIN, envoy_serial_num),
        )
        super().__init__(coordinator)

    @property
    def native_value(self) -> datetime.datetime | float:
        """Return the state of the sensor."""
        envoy = self.coordinator.envoy
        assert envoy.data is not None
        assert envoy.data.inverters is not None
        inverter = envoy.data.inverters[self._serial_number]
        return self.entity_description.value_fn(inverter)
