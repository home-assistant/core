"""Support for Fronius devices."""
from __future__ import annotations

import logging
from typing import Any

from pyfronius import Fronius
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS,
    CONF_RESOURCE,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_POWER_FACTOR,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_WATT_HOUR,
    FREQUENCY_HERTZ,
    PERCENTAGE,
    POWER_VOLT_AMPERE,
    POWER_WATT,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FroniusSolarNet
from .const import DOMAIN
from .coordinator import (
    FroniusCoordinatorBase,
    FroniusInverterUpdateCoordinator,
    FroniusLoggerUpdateCoordinator,
    FroniusMeterUpdateCoordinator,
    FroniusPowerFlowUpdateCoordinator,
    FroniusStorageUpdateCoordinator,
)

_LOGGER = logging.getLogger(__name__)

ELECTRIC_CHARGE_AMPERE_HOURS = "Ah"
ENERGY_VOLT_AMPERE_REACTIVE_HOUR = "varh"
POWER_VOLT_AMPERE_REACTIVE = "var"

PLATFORM_SCHEMA = vol.All(
    cv.deprecated(CONF_MONITORED_CONDITIONS),
    PLATFORM_SCHEMA.extend(
        {
            vol.Required(CONF_RESOURCE): cv.url,
            vol.Required(CONF_MONITORED_CONDITIONS): object,
        }
    ),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: None = None,
) -> None:
    """Import Fronius configuration from yaml."""
    host = config[CONF_RESOURCE]
    fronius = Fronius(async_get_clientsession(hass), host)
    solar_net = FroniusSolarNet(hass, fronius, host)
    await solar_net.init_devices()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][host] = solar_net

    for inverter_coordinator in solar_net.inverter_coordinators:
        inverter_coordinator.add_entities_for_seen_keys(
            async_add_entities, InverterSensor
        )
    if solar_net.logger_coordinator is not None:
        solar_net.logger_coordinator.add_entities_for_seen_keys(
            async_add_entities, LoggerSensor
        )
    if solar_net.meter_coordinator is not None:
        solar_net.meter_coordinator.add_entities_for_seen_keys(
            async_add_entities, MeterSensor
        )
    if solar_net.power_flow_coordinator is not None:
        solar_net.power_flow_coordinator.add_entities_for_seen_keys(
            async_add_entities, PowerFlowSensor
        )
    if solar_net.storage_coordinator is not None:
        solar_net.storage_coordinator.add_entities_for_seen_keys(
            async_add_entities, StorageSensor
        )


INVERTER_ENTITY_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    "energy_day": SensorEntityDescription(
        key="energy_day",
        name="Energy day",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    "energy_year": SensorEntityDescription(
        key="energy_year",
        name="Energy year",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    "energy_total": SensorEntityDescription(
        key="energy_total",
        name="Energy total",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    "frequency_ac": SensorEntityDescription(
        key="frequency_ac",
        name="Frequency AC",
        native_unit_of_measurement=FREQUENCY_HERTZ,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "current_ac": SensorEntityDescription(
        key="current_ac",
        name="AC Current",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "current_dc": SensorEntityDescription(
        key="current_dc",
        name="DC current",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:current-dc",
    ),
    "current_dc_2": SensorEntityDescription(
        key="current_dc_2",
        name="DC Current 2",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:current-dc",
    ),
    "power_ac": SensorEntityDescription(
        key="power_ac",
        name="AC power",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "voltage_ac": SensorEntityDescription(
        key="voltage_ac",
        name="AC voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "voltage_dc": SensorEntityDescription(
        key="voltage_dc",
        name="DC voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:current-dc",
    ),
    "voltage_dc_2": SensorEntityDescription(
        key="voltage_dc_2",
        name="DC voltage 2",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:current-dc",
    ),
}

LOGGER_ENTITY_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    "co2_factor": SensorEntityDescription(
        key="co2_factor",
        name="CO₂ factor",
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:molecule-co2",
    ),
    "cash_factor": SensorEntityDescription(
        key="cash_factor",
        name="Grid export tariff",
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:cash-plus",
    ),
    "delivery_factor": SensorEntityDescription(
        key="delivery_factor",
        name="Grid import tariff",
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:cash-minus",
    ),
}

METER_ENTITY_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    "current_ac_phase_1": SensorEntityDescription(
        key="current_ac_phase_1",
        name="Current AC phase 1",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "current_ac_phase_2": SensorEntityDescription(
        key="current_ac_phase_2",
        name="Current AC phase 2",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "current_ac_phase_3": SensorEntityDescription(
        key="current_ac_phase_3",
        name="Current AC phase 3",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "energy_reactive_ac_consumed": SensorEntityDescription(
        key="energy_reactive_ac_consumed",
        name="Energy Reactive AC consumed",
        native_unit_of_measurement=ENERGY_VOLT_AMPERE_REACTIVE_HOUR,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        icon="mdi:lightning-bolt-outline",
    ),
    "energy_reactive_ac_produced": SensorEntityDescription(
        key="energy_reactive_ac_produced",
        name="Energy Reactive AC produced",
        native_unit_of_measurement=ENERGY_VOLT_AMPERE_REACTIVE_HOUR,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        icon="mdi:lightning-bolt-outline",
    ),
    "energy_real_ac_minus": SensorEntityDescription(
        key="energy_real_ac_minus",
        name="Energy real AC minus",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    "energy_real_ac_plus": SensorEntityDescription(
        key="energy_real_ac_plus",
        name="Energy real AC plus",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    "energy_real_consumed": SensorEntityDescription(
        key="energy_real_consumed",
        name="Energy real consumed",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    "energy_real_produced": SensorEntityDescription(
        key="energy_real_produced",
        name="Energy real produced",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    "frequency_phase_average": SensorEntityDescription(
        key="frequency_phase_average",
        name="Frequency phase average",
        native_unit_of_measurement=FREQUENCY_HERTZ,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "power_apparent_phase_1": SensorEntityDescription(
        key="power_apparent_phase_1",
        name="Power apparent phase 1",
        native_unit_of_measurement=POWER_VOLT_AMPERE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:flash-outline",
    ),
    "power_apparent_phase_2": SensorEntityDescription(
        key="power_apparent_phase_2",
        name="Power apparent phase 2",
        native_unit_of_measurement=POWER_VOLT_AMPERE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:flash-outline",
    ),
    "power_apparent_phase_3": SensorEntityDescription(
        key="power_apparent_phase_3",
        name="Power apparent phase 3",
        native_unit_of_measurement=POWER_VOLT_AMPERE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:flash-outline",
    ),
    "power_apparent": SensorEntityDescription(
        key="power_apparent",
        name="Power apparent",
        native_unit_of_measurement=POWER_VOLT_AMPERE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:flash-outline",
    ),
    "power_factor_phase_1": SensorEntityDescription(
        key="power_factor_phase_1",
        name="Power factor phase 1",
        device_class=DEVICE_CLASS_POWER_FACTOR,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "power_factor_phase_2": SensorEntityDescription(
        key="power_factor_phase_2",
        name="Power factor phase 2",
        device_class=DEVICE_CLASS_POWER_FACTOR,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "power_factor_phase_3": SensorEntityDescription(
        key="power_factor_phase_3",
        name="Power factor phase 3",
        device_class=DEVICE_CLASS_POWER_FACTOR,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "power_factor": SensorEntityDescription(
        key="power_factor",
        name="Power factor",
        device_class=DEVICE_CLASS_POWER_FACTOR,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "power_reactive_phase_1": SensorEntityDescription(
        key="power_reactive_phase_1",
        name="Power reactive phase 1",
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:flash-outline",
    ),
    "power_reactive_phase_2": SensorEntityDescription(
        key="power_reactive_phase_2",
        name="Power reactive phase 2",
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:flash-outline",
    ),
    "power_reactive_phase_3": SensorEntityDescription(
        key="power_reactive_phase_3",
        name="Power reactive phase 3",
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:flash-outline",
    ),
    "power_reactive": SensorEntityDescription(
        key="power_reactive",
        name="Power reactive",
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:flash-outline",
    ),
    "power_real_phase_1": SensorEntityDescription(
        key="power_real_phase_1",
        name="Power real phase 1",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "power_real_phase_2": SensorEntityDescription(
        key="power_real_phase_2",
        name="Power real phase 2",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "power_real_phase_3": SensorEntityDescription(
        key="power_real_phase_3",
        name="Power real phase 3",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "power_real": SensorEntityDescription(
        key="power_real",
        name="Power real",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "voltage_ac_phase_1": SensorEntityDescription(
        key="voltage_ac_phase_1",
        name="Voltage AC phase 1",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "voltage_ac_phase_2": SensorEntityDescription(
        key="voltage_ac_phase_2",
        name="Voltage AC phase 2",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "voltage_ac_phase_3": SensorEntityDescription(
        key="voltage_ac_phase_3",
        name="Voltage AC phase 3",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "voltage_ac_phase_to_phase_12": SensorEntityDescription(
        key="voltage_ac_phase_to_phase_12",
        name="Voltage AC phase 1-2",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "voltage_ac_phase_to_phase_23": SensorEntityDescription(
        key="voltage_ac_phase_to_phase_23",
        name="Voltage AC phase 2-3",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "voltage_ac_phase_to_phase_31": SensorEntityDescription(
        key="voltage_ac_phase_to_phase_31",
        name="Voltage AC phase 3-1",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
}

POWER_FLOW_ENTITY_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    "energy_day": SensorEntityDescription(
        key="energy_day",
        name="Energy day",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    "energy_year": SensorEntityDescription(
        key="energy_year",
        name="Energy year",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    "energy_total": SensorEntityDescription(
        key="energy_total",
        name="Energy total",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    "power_battery": SensorEntityDescription(
        key="power_battery",
        name="Power battery",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "power_grid": SensorEntityDescription(
        key="power_grid",
        name="Power grid",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "power_load": SensorEntityDescription(
        key="power_load",
        name="Power load",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "power_photovoltaics": SensorEntityDescription(
        key="power_photovoltaics",
        name="Power photovoltaics",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "relative_autonomy": SensorEntityDescription(
        key="relative_autonomy",
        name="Relative autonomy",
        native_unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:home-circle-outline",
    ),
    "relative_self_consumption": SensorEntityDescription(
        key="relative_self_consumption",
        name="Relative self consumption",
        native_unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:solar-power",
    ),
}

STORAGE_ENTITY_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    "capacity_maximum": SensorEntityDescription(
        key="capacity_maximum",
        name="Capacity maximum",
        native_unit_of_measurement=ELECTRIC_CHARGE_AMPERE_HOURS,
    ),
    "capacity_designed": SensorEntityDescription(
        key="capacity_designed",
        name="Capacity designed",
        native_unit_of_measurement=ELECTRIC_CHARGE_AMPERE_HOURS,
    ),
    "current_dc": SensorEntityDescription(
        key="current_dc",
        name="Current DC",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:current-dc",
    ),
    "voltage_dc": SensorEntityDescription(
        key="voltage_dc",
        name="Voltage DC",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:current-dc",
    ),
    "voltage_dc_maximum_cell": SensorEntityDescription(
        key="voltage_dc_maximum_cell",
        name="Voltage DC maximum cell",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:current-dc",
    ),
    "voltage_dc_minimum_cell": SensorEntityDescription(
        key="voltage_dc_minimum_cell",
        name="Voltage DC minimum cell",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:current-dc",
    ),
    "state_of_charge": SensorEntityDescription(
        key="state_of_charge",
        name="State of charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_BATTERY,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "temperature_cell": SensorEntityDescription(
        key="temperature_cell",
        name="Temperature cell",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
}


class _FroniusSensorEntity(CoordinatorEntity, SensorEntity):
    """Defines a Fronius coordinator entity."""

    coordinator: FroniusCoordinatorBase
    entity_descriptions: dict[str, SensorEntityDescription]

    def __init__(
        self,
        coordinator: FroniusCoordinatorBase,
        key: str,
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius meter sensor."""
        super().__init__(coordinator)
        self.entity_description = self.entity_descriptions[key]
        self.solar_net_id = solar_net_id
        self._attr_native_value = self._get_entity_value()

    def _device_data(self) -> dict[str, Any]:
        """Extract information for SolarNet device from coordinator data."""
        return self.coordinator.data[self.solar_net_id]

    def _get_entity_value(self) -> Any:
        """Extract entity value from coordinator. Raises KeyError if not included in latest update."""
        new_value = self.coordinator.data[self.solar_net_id][
            self.entity_description.key
        ]["value"]
        return round(new_value, 4) if isinstance(new_value, float) else new_value

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            self._attr_native_value = self._get_entity_value()
        except KeyError:
            return
        self.async_write_ha_state()


class InverterSensor(_FroniusSensorEntity):
    """Defines a Fronius inverter device sensor entity."""

    coordinator: FroniusInverterUpdateCoordinator
    entity_descriptions = INVERTER_ENTITY_DESCRIPTIONS

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Set up an individual Fronius inverter sensor."""
        super().__init__(*args, **kwargs)
        self._attr_name = (
            f"Fronius Inverter {self.solar_net_id} - {self.entity_description.name}"
        )
        self._attr_unique_id = (
            f"{self.coordinator.inverter_info.unique_id}-{self.entity_description.key}"
        )


class LoggerSensor(_FroniusSensorEntity):
    """Defines a Fronius logger device sensor entity."""

    coordinator: FroniusLoggerUpdateCoordinator
    entity_descriptions = LOGGER_ENTITY_DESCRIPTIONS

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Set up an individual Fronius meter sensor."""
        super().__init__(*args, **kwargs)
        logger_data = self._device_data()
        self._attr_name = f"Fronius Logger - {self.entity_description.name}"
        self._attr_native_unit_of_measurement = logger_data[
            self.entity_description.key
        ].get("unit")
        self._attr_unique_id = (
            f'{logger_data["unique_identifier"]["value"]}-{self.entity_description.key}'
        )


class MeterSensor(_FroniusSensorEntity):
    """Defines a Fronius meter device sensor entity."""

    coordinator: FroniusMeterUpdateCoordinator
    entity_descriptions = METER_ENTITY_DESCRIPTIONS

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Set up an individual Fronius meter sensor."""
        super().__init__(*args, **kwargs)
        meter_data = self._device_data()

        self._attr_name = (
            f"Fronius Meter {self.solar_net_id} - {self.entity_description.name}"
        )
        self._attr_unique_id = (
            f'{meter_data["serial"]["value"]}-{self.entity_description.key}'
        )


class PowerFlowSensor(_FroniusSensorEntity):
    """Defines a Fronius power flow sensor entity."""

    coordinator: FroniusPowerFlowUpdateCoordinator
    entity_descriptions = POWER_FLOW_ENTITY_DESCRIPTIONS

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Set up an individual Fronius power flow sensor."""
        super().__init__(*args, **kwargs)
        self._attr_name = f"Fronius power flow - {self.entity_description.name}"
        self._attr_unique_id = (
            f"{self.coordinator.solar_net.solar_net_device_id}"
            f"-power_flow-{self.entity_description.key}"
        )


class StorageSensor(_FroniusSensorEntity):
    """Defines a Fronius storage device sensor entity."""

    coordinator: FroniusStorageUpdateCoordinator
    entity_descriptions = STORAGE_ENTITY_DESCRIPTIONS

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Set up an individual Fronius storage sensor."""
        super().__init__(*args, **kwargs)
        storage_data = self._device_data()

        self._attr_name = (
            f"Fronius Storage {self.solar_net_id} - {self.entity_description.name}"
        )
        self._attr_unique_id = (
            f'{storage_data["serial"]["value"]}-{self.entity_description.key}'
        )
