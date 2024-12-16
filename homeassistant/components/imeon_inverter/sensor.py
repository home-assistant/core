"""Imeon inverter sensor support."""

import logging

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import InverterCoordinator

type InverterConfigEntry = ConfigEntry[InverterCoordinator]

_LOGGER = logging.getLogger(__name__)


ENTITY_DESCRIPTIONS = (
    # Battery
    SensorEntityDescription(
        key="battery_autonomy",
        name="Battery autonomy",
        native_unit_of_measurement="",
        icon="mdi:battery-clock",
    ),
    SensorEntityDescription(
        key="battery_charge_time",
        name="Battery charge time",
        native_unit_of_measurement="",
        icon="mdi:battery-charging",
    ),
    SensorEntityDescription(
        key="battery_power",
        name="Battery power",
        native_unit_of_measurement="W",
        icon="mdi:battery",
    ),
    SensorEntityDescription(
        key="battery_soc",
        name="Battery SOC",
        native_unit_of_measurement="%",
        icon="mdi:battery-charging-100",
    ),
    SensorEntityDescription(
        key="battery_stored",
        name="Battery stored",
        native_unit_of_measurement="Wh",
        icon="mdi:battery",
    ),
    # Grid
    SensorEntityDescription(
        key="grid_current_l1",
        name="Grid current L1",
        native_unit_of_measurement="A",
        icon="mdi:current-ac",
    ),
    SensorEntityDescription(
        key="grid_current_l2",
        name="Grid current L2",
        native_unit_of_measurement="A",
        icon="mdi:current-ac",
    ),
    SensorEntityDescription(
        key="grid_current_l3",
        name="Grid current L3",
        native_unit_of_measurement="A",
        icon="mdi:current-ac",
    ),
    SensorEntityDescription(
        key="grid_frequency",
        name="Grid frequency",
        native_unit_of_measurement="Hz",
        icon="mdi:sine-wave",
    ),
    SensorEntityDescription(
        key="grid_voltage_l1",
        name="Grid voltage L1",
        native_unit_of_measurement="V",
        icon="mdi:flash",
    ),
    SensorEntityDescription(
        key="grid_voltage_l2",
        name="Grid voltage L2",
        native_unit_of_measurement="V",
        icon="mdi:flash",
    ),
    SensorEntityDescription(
        key="grid_voltage_l3",
        name="Grid voltage L3",
        native_unit_of_measurement="V",
        icon="mdi:flash",
    ),
    # AC Input
    SensorEntityDescription(
        key="input_power_l1",
        name="Input power L1",
        native_unit_of_measurement="W",
        icon="mdi:power-socket",
    ),
    SensorEntityDescription(
        key="input_power_l2",
        name="Input power L2",
        native_unit_of_measurement="W",
        icon="mdi:power-socket",
    ),
    SensorEntityDescription(
        key="input_power_l3",
        name="Input power L3",
        native_unit_of_measurement="W",
        icon="mdi:power-socket",
    ),
    SensorEntityDescription(
        key="input_power_total",
        name="Input power total",
        native_unit_of_measurement="W",
        icon="mdi:power-plug",
    ),
    # Inverter settings
    SensorEntityDescription(
        key="inverter_charging_current_limit",
        name="Inverter charging current limit",
        native_unit_of_measurement="A",
        icon="mdi:current-dc",
    ),
    SensorEntityDescription(
        key="inverter_injection_power_limit",
        name="Inverter injection power limit",
        native_unit_of_measurement="W",
        icon="mdi:power-socket",
    ),
    # Electric Meter
    SensorEntityDescription(
        key="meter_power",
        name="Meter power",
        native_unit_of_measurement="W",
        icon="mdi:power-plug",
    ),
    SensorEntityDescription(
        key="meter_power_protocol",
        name="Meter power protocol",
        native_unit_of_measurement="W",
        icon="mdi:protocol",
    ),
    # AC Output
    SensorEntityDescription(
        key="output_current_l1",
        name="Output current L1",
        native_unit_of_measurement="A",
        icon="mdi:current-ac",
    ),
    SensorEntityDescription(
        key="output_current_l2",
        name="Output current L2",
        native_unit_of_measurement="A",
        icon="mdi:current-ac",
    ),
    SensorEntityDescription(
        key="output_current_l3",
        name="Output current L3",
        native_unit_of_measurement="A",
        icon="mdi:current-ac",
    ),
    SensorEntityDescription(
        key="output_frequency",
        name="Output frequency",
        native_unit_of_measurement="Hz",
        icon="mdi:sine-wave",
    ),
    SensorEntityDescription(
        key="output_power_l1",
        name="Output power L1",
        native_unit_of_measurement="W",
        icon="mdi:power-socket",
    ),
    SensorEntityDescription(
        key="output_power_l2",
        name="Output power L2",
        native_unit_of_measurement="W",
        icon="mdi:power-socket",
    ),
    SensorEntityDescription(
        key="output_power_l3",
        name="Output power L3",
        native_unit_of_measurement="W",
        icon="mdi:power-socket",
    ),
    SensorEntityDescription(
        key="output_power_total",
        name="Output power total",
        native_unit_of_measurement="W",
        icon="mdi:power-plug",
    ),
    SensorEntityDescription(
        key="output_voltage_l1",
        name="Output voltage L1",
        native_unit_of_measurement="V",
        icon="mdi:flash",
    ),
    SensorEntityDescription(
        key="output_voltage_l2",
        name="Output voltage L2",
        native_unit_of_measurement="V",
        icon="mdi:flash",
    ),
    SensorEntityDescription(
        key="output_voltage_l3",
        name="Output voltage L3",
        native_unit_of_measurement="V",
        icon="mdi:flash",
    ),
    # Solar Panel
    SensorEntityDescription(
        key="pv_consumed",
        name="PV consumed",
        native_unit_of_measurement="Wh",
        icon="mdi:solar-power",
    ),
    SensorEntityDescription(
        key="pv_injected",
        name="PV injected",
        native_unit_of_measurement="Wh",
        icon="mdi:solar-power",
    ),
    SensorEntityDescription(
        key="pv_power_1",
        name="PV power 1",
        native_unit_of_measurement="W",
        icon="mdi:solar-power",
    ),
    SensorEntityDescription(
        key="pv_power_2",
        name="PV power 2",
        native_unit_of_measurement="W",
        icon="mdi:solar-power",
    ),
    SensorEntityDescription(
        key="pv_power_total",
        name="PV power total",
        native_unit_of_measurement="W",
        icon="mdi:solar-power",
    ),
    # Temperature
    SensorEntityDescription(
        key="temp_air_temperature",
        name="Air temperature",
        native_unit_of_measurement="°C",
        icon="mdi:thermometer",
    ),
    SensorEntityDescription(
        key="temp_component_temperature",
        name="Component temperature",
        native_unit_of_measurement="°C",
        icon="mdi:thermometer",
    ),
    # Monitoring (data over the last 24 hours)
    SensorEntityDescription(
        key="monitoring_building_consumption",
        name="Building consumption",
        native_unit_of_measurement="Wh",
        icon="mdi:home-lightning-bolt",
    ),
    SensorEntityDescription(
        key="monitoring_economy_factor",
        name="Economy factor",
        native_unit_of_measurement="",
        icon="mdi:chart-bar",
    ),
    SensorEntityDescription(
        key="monitoring_grid_consumption",
        name="Grid consumption",
        native_unit_of_measurement="Wh",
        icon="mdi:transmission-tower",
    ),
    SensorEntityDescription(
        key="monitoring_grid_injection",
        name="Grid injection",
        native_unit_of_measurement="Wh",
        icon="mdi:transmission-tower-export",
    ),
    SensorEntityDescription(
        key="monitoring_grid_power_flow",
        name="Grid power flow",
        native_unit_of_measurement="Wh",
        icon="mdi:power-plug",
    ),
    SensorEntityDescription(
        key="monitoring_self_consumption",
        name="Self consumption",
        native_unit_of_measurement="%",
        icon="mdi:percent",
    ),
    SensorEntityDescription(
        key="monitoring_self_production",
        name="Self production",
        native_unit_of_measurement="%",
        icon="mdi:percent",
    ),
    SensorEntityDescription(
        key="monitoring_solar_production",
        name="Solar production",
        native_unit_of_measurement="Wh",
        icon="mdi:solar-power",
    ),
    # Monitoring (instant minute data)
    SensorEntityDescription(
        key="monitoring_minute_building_consumption",
        name="Minute building consumption",
        native_unit_of_measurement="W",
        icon="mdi:home-lightning-bolt",
    ),
    SensorEntityDescription(
        key="monitoring_minute_grid_consumption",
        name="Minute grid consumption",
        native_unit_of_measurement="W",
        icon="mdi:transmission-tower",
    ),
    SensorEntityDescription(
        key="monitoring_minute_grid_injection",
        name="Minute grid injection",
        native_unit_of_measurement="W",
        icon="mdi:transmission-tower-export",
    ),
    SensorEntityDescription(
        key="monitoring_minute_grid_power_flow",
        name="Minute grid power flow",
        native_unit_of_measurement="W",
        icon="mdi:power-plug",
    ),
    SensorEntityDescription(
        key="monitoring_minute_solar_production",
        name="Minute solar production",
        native_unit_of_measurement="W",
        icon="mdi:solar-power",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InverterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create each sensor for a given config entry."""

    # Get Inverter from UUID
    coordinator: InverterCoordinator = entry.runtime_data

    # Init sensor entities
    entities = [
        InverterSensor(coordinator, entry, description)
        for description in ENTITY_DESCRIPTIONS
    ]

    async_add_entities(entities, True)


class InverterSensor(CoordinatorEntity[InverterCoordinator], SensorEntity):
    """A sensor that returns numerical values with units."""

    def __init__(
        self,
        coordinator: InverterCoordinator,
        entry: InverterConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.entity_description = description
        self.data_key = description.key
        self._attr_translation_key = description.key
        self._attr_unique_id = f"{entry.entry_id}_{self.data_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data["address"],
            manufacturer="Imeon Energy",
            model="Home Assistant Integration",
            sw_version="1.0",
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            self._attr_native_value = self.coordinator.data.get(self.data_key)
        except (TypeError, ValueError):
            self._attr_native_value = None
        self.async_write_ha_state()
