"""Platform for sensor integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    POWER_VOLT_AMPERE_REACTIVE,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HuaweiSmartLogger3000DataCoordinator

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_SENSOR_FORMAT = DOMAIN + ".huaweismartlogger3000_{}"


@dataclass(kw_only=True, frozen=True)
class HuaweiSmartLogger3000EntityDescription(SensorEntityDescription):
    """Sensor class definition."""

    value: Callable = float


SENSOR_TYPES: tuple[HuaweiSmartLogger3000EntityDescription, ...] = (
    HuaweiSmartLogger3000EntityDescription(
        key="soc",
        translation_key="soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HuaweiSmartLogger3000EntityDescription(
        key="current_day_feedin_to_grid",
        translation_key="current_day_feedin_to_grid",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HuaweiSmartLogger3000EntityDescription(
        key="gridtied_active_power",
        translation_key="gridtied_active_power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HuaweiSmartLogger3000EntityDescription(
        key="gridtied_reactive_power",
        translation_key="gridtied_reactive_power",
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HuaweiSmartLogger3000EntityDescription(
        key="load_power",
        translation_key="load_power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HuaweiSmartLogger3000EntityDescription(
        key="active_power",
        translation_key="active_power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HuaweiSmartLogger3000EntityDescription(
        key="reactive_power",
        translation_key="reactive_power",
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HuaweiSmartLogger3000EntityDescription(
        key="todays_power_supply_from_grid",
        translation_key="todays_power_supply_from_grid",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HuaweiSmartLogger3000EntityDescription(
        key="current_day_supply_from_grid",
        translation_key="current_day_supply_from_grid",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HuaweiSmartLogger3000EntityDescription(
        key="current_day_consumption",
        translation_key="current_day_consumption",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HuaweiSmartLogger3000EntityDescription(
        key="total_power_supply_from_grid",
        translation_key="total_power_supply_from_grid",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HuaweiSmartLogger3000EntityDescription(
        key="total_supply_from_grid",
        translation_key="total_supply_from_grid",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HuaweiSmartLogger3000EntityDescription(
        key="total_feedin_to_grid",
        translation_key="total_feedin_to_grid",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HuaweiSmartLogger3000EntityDescription(
        key="total_power_consumption",
        translation_key="total_power_consumption",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HuaweiSmartLogger3000EntityDescription(
        key="pv_output_power",
        translation_key="pv_output_power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HuaweiSmartLogger3000EntityDescription(
        key="battery_chargedischarge_power",
        translation_key="battery_chargedischarge_power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HuaweiSmartLogger3000EntityDescription(
        key="reactive_pv_power",
        translation_key="reactive_pv_power",
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HuaweiSmartLogger3000EntityDescription(
        key="reactive_ess_power",
        translation_key="reactive_ess_power",
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HuaweiSmartLogger3000EntityDescription(
        key="currentday_charge_capacity",
        translation_key="currentday_charge_capacity",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HuaweiSmartLogger3000EntityDescription(
        key="currentday_discharge_capacity",
        translation_key="currentday_discharge_capacity",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HuaweiSmartLogger3000EntityDescription(
        key="total_charge",
        translation_key="total_charge",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HuaweiSmartLogger3000EntityDescription(
        key="total_discharge",
        translation_key="total_discharge",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HuaweiSmartLogger3000EntityDescription(
        key="rated_ess_power",
        translation_key="rated_ess_power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Huawei Smart Loggers sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    _LOGGER.debug("In sensor.py async_setup_entry")
    async_add_entities(
        HuaweiSmartLogger3000Sensor(coordinator, description)
        for description in SENSOR_TYPES
    )


class HuaweiSmartLogger3000Sensor(
    CoordinatorEntity[HuaweiSmartLogger3000DataCoordinator], SensorEntity
):
    """Implementation of a speedtest.net sensor."""

    _attr_has_entity_name = True

    entity_description: HuaweiSmartLogger3000EntityDescription

    def __init__(
        self,
        coordinator: HuaweiSmartLogger3000DataCoordinator,
        description: HuaweiSmartLogger3000EntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.entity_id = ENTITY_ID_SENSOR_FORMAT.format(description.key)
        self._attr_unique_id = f"huaweismartlogger3000_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.api.HOST)},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Huawei",
            model="Smart Logger 3000",
            configuration_url=f"https://{coordinator.api.HOST}",
        )

    @property
    def native_value(self) -> StateType:
        """Return native value for entity."""
        if self.coordinator.data:
            return self.coordinator.data.get(self.entity_description.key)
        return None
