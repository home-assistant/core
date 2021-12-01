"""Support for Fronius devices."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    PLATFORM_SCHEMA,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS,
    CONF_RESOURCE,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_FREQUENCY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_POWER_FACTOR,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_WATT_HOUR,
    ENTITY_CATEGORY_DIAGNOSTIC,
    FREQUENCY_HERTZ,
    PERCENTAGE,
    POWER_VOLT_AMPERE,
    POWER_WATT,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from . import FroniusSolarNet
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
    PLATFORM_SCHEMA.extend(
        {
            vol.Required(CONF_RESOURCE): cv.url,
            vol.Optional(CONF_MONITORED_CONDITIONS): object,
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
    _LOGGER.warning(
        "Loading Fronius via platform setup is deprecated. Please remove it from your yaml configuration"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Fronius sensor entities based on a config entry."""
    solar_net: FroniusSolarNet = hass.data[DOMAIN][config_entry.entry_id]
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


INVERTER_ENTITY_DESCRIPTIONS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key="energy_day",
        name="Energy day",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="energy_year",
        name="Energy year",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="energy_total",
        name="Energy total",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="frequency_ac",
        name="Frequency AC",
        native_unit_of_measurement=FREQUENCY_HERTZ,
        device_class=DEVICE_CLASS_FREQUENCY,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="current_ac",
        name="AC Current",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="current_dc",
        name="DC current",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:current-dc",
    ),
    SensorEntityDescription(
        key="current_dc_2",
        name="DC Current 2",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:current-dc",
    ),
    SensorEntityDescription(
        key="power_ac",
        name="AC power",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="voltage_ac",
        name="AC voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="voltage_dc",
        name="DC voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:current-dc",
    ),
    SensorEntityDescription(
        key="voltage_dc_2",
        name="DC voltage 2",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:current-dc",
    ),
    # device status entities
    SensorEntityDescription(
        key="inverter_state",
        name="Inverter state",
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="error_code",
        name="Error code",
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="status_code",
        name="Status code",
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="led_state",
        name="LED state",
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="led_color",
        name="LED color",
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
]

LOGGER_ENTITY_DESCRIPTIONS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key="co2_factor",
        name="CO₂ factor",
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:molecule-co2",
    ),
    SensorEntityDescription(
        key="cash_factor",
        name="Grid export tariff",
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:cash-plus",
    ),
    SensorEntityDescription(
        key="delivery_factor",
        name="Grid import tariff",
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:cash-minus",
    ),
]

METER_ENTITY_DESCRIPTIONS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key="current_ac_phase_1",
        name="Current AC phase 1",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="current_ac_phase_2",
        name="Current AC phase 2",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="current_ac_phase_3",
        name="Current AC phase 3",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="energy_reactive_ac_consumed",
        name="Energy reactive AC consumed",
        native_unit_of_measurement=ENERGY_VOLT_AMPERE_REACTIVE_HOUR,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        icon="mdi:lightning-bolt-outline",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="energy_reactive_ac_produced",
        name="Energy reactive AC produced",
        native_unit_of_measurement=ENERGY_VOLT_AMPERE_REACTIVE_HOUR,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        icon="mdi:lightning-bolt-outline",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="energy_real_ac_minus",
        name="Energy real AC minus",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="energy_real_ac_plus",
        name="Energy real AC plus",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="energy_real_consumed",
        name="Energy real consumed",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="energy_real_produced",
        name="Energy real produced",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="frequency_phase_average",
        name="Frequency phase average",
        native_unit_of_measurement=FREQUENCY_HERTZ,
        device_class=DEVICE_CLASS_FREQUENCY,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="meter_location",
        name="Meter location",
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="power_apparent_phase_1",
        name="Power apparent phase 1",
        native_unit_of_measurement=POWER_VOLT_AMPERE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:flash-outline",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="power_apparent_phase_2",
        name="Power apparent phase 2",
        native_unit_of_measurement=POWER_VOLT_AMPERE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:flash-outline",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="power_apparent_phase_3",
        name="Power apparent phase 3",
        native_unit_of_measurement=POWER_VOLT_AMPERE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:flash-outline",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="power_apparent",
        name="Power apparent",
        native_unit_of_measurement=POWER_VOLT_AMPERE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:flash-outline",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="power_factor_phase_1",
        name="Power factor phase 1",
        device_class=DEVICE_CLASS_POWER_FACTOR,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="power_factor_phase_2",
        name="Power factor phase 2",
        device_class=DEVICE_CLASS_POWER_FACTOR,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="power_factor_phase_3",
        name="Power factor phase 3",
        device_class=DEVICE_CLASS_POWER_FACTOR,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="power_factor",
        name="Power factor",
        device_class=DEVICE_CLASS_POWER_FACTOR,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="power_reactive_phase_1",
        name="Power reactive phase 1",
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:flash-outline",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="power_reactive_phase_2",
        name="Power reactive phase 2",
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:flash-outline",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="power_reactive_phase_3",
        name="Power reactive phase 3",
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:flash-outline",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="power_reactive",
        name="Power reactive",
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:flash-outline",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="power_real_phase_1",
        name="Power real phase 1",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="power_real_phase_2",
        name="Power real phase 2",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="power_real_phase_3",
        name="Power real phase 3",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="power_real",
        name="Power real",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="voltage_ac_phase_1",
        name="Voltage AC phase 1",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="voltage_ac_phase_2",
        name="Voltage AC phase 2",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="voltage_ac_phase_3",
        name="Voltage AC phase 3",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="voltage_ac_phase_to_phase_12",
        name="Voltage AC phase 1-2",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="voltage_ac_phase_to_phase_23",
        name="Voltage AC phase 2-3",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="voltage_ac_phase_to_phase_31",
        name="Voltage AC phase 3-1",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
]

POWER_FLOW_ENTITY_DESCRIPTIONS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key="energy_day",
        name="Energy day",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="energy_year",
        name="Energy year",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="energy_total",
        name="Energy total",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="meter_mode",
        name="Mode",
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="power_battery",
        name="Power battery",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="power_grid",
        name="Power grid",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="power_load",
        name="Power load",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="power_photovoltaics",
        name="Power photovoltaics",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="relative_autonomy",
        name="Relative autonomy",
        native_unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:home-circle-outline",
    ),
    SensorEntityDescription(
        key="relative_self_consumption",
        name="Relative self consumption",
        native_unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:solar-power",
    ),
]

STORAGE_ENTITY_DESCRIPTIONS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key="capacity_maximum",
        name="Capacity maximum",
        native_unit_of_measurement=ELECTRIC_CHARGE_AMPERE_HOURS,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="capacity_designed",
        name="Capacity designed",
        native_unit_of_measurement=ELECTRIC_CHARGE_AMPERE_HOURS,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="current_dc",
        name="Current DC",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:current-dc",
    ),
    SensorEntityDescription(
        key="voltage_dc",
        name="Voltage DC",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:current-dc",
    ),
    SensorEntityDescription(
        key="voltage_dc_maximum_cell",
        name="Voltage DC maximum cell",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:current-dc",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="voltage_dc_minimum_cell",
        name="Voltage DC minimum cell",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:current-dc",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="state_of_charge",
        name="State of charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_BATTERY,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="temperature_cell",
        name="Temperature cell",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
]


class _FroniusSensorEntity(CoordinatorEntity, SensorEntity):
    """Defines a Fronius coordinator entity."""

    coordinator: FroniusCoordinatorBase
    entity_descriptions: list[SensorEntityDescription]
    _entity_id_prefix: str

    def __init__(
        self,
        coordinator: FroniusCoordinatorBase,
        key: str,
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius meter sensor."""
        super().__init__(coordinator)
        self.entity_description = next(
            desc for desc in self.entity_descriptions if desc.key == key
        )
        # default entity_id added 2021.12
        # used for migration from non-unique_id entities of previous integration implementation
        # when removed after migration period `_entity_id_prefix` will also no longer be needed
        self.entity_id = f"{SENSOR_DOMAIN}.{key}_{DOMAIN}_{self._entity_id_prefix}_{coordinator.solar_net.host}"
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

    entity_descriptions = INVERTER_ENTITY_DESCRIPTIONS

    def __init__(
        self,
        coordinator: FroniusInverterUpdateCoordinator,
        key: str,
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius inverter sensor."""
        self._entity_id_prefix = f"inverter_{solar_net_id}"
        super().__init__(coordinator, key, solar_net_id)
        # device_info created in __init__ from a `GetInverterInfo` request
        self._attr_device_info = coordinator.inverter_info.device_info
        self._attr_unique_id = f"{coordinator.inverter_info.unique_id}-{key}"


class LoggerSensor(_FroniusSensorEntity):
    """Defines a Fronius logger device sensor entity."""

    entity_descriptions = LOGGER_ENTITY_DESCRIPTIONS
    _entity_id_prefix = "logger_info_0"

    def __init__(
        self,
        coordinator: FroniusLoggerUpdateCoordinator,
        key: str,
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius meter sensor."""
        super().__init__(coordinator, key, solar_net_id)
        logger_data = self._device_data()
        # Logger device is already created in FroniusSolarNet._create_solar_net_device
        self._attr_device_info = coordinator.solar_net.system_device_info
        self._attr_native_unit_of_measurement = logger_data[key].get("unit")
        self._attr_unique_id = f'{logger_data["unique_identifier"]["value"]}-{key}'


class MeterSensor(_FroniusSensorEntity):
    """Defines a Fronius meter device sensor entity."""

    entity_descriptions = METER_ENTITY_DESCRIPTIONS

    def __init__(
        self,
        coordinator: FroniusMeterUpdateCoordinator,
        key: str,
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius meter sensor."""
        self._entity_id_prefix = f"meter_{solar_net_id}"
        super().__init__(coordinator, key, solar_net_id)
        meter_data = self._device_data()

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, meter_data["serial"]["value"])},
            manufacturer=meter_data["manufacturer"]["value"],
            model=meter_data["model"]["value"],
            name=meter_data["model"]["value"],
            via_device=(DOMAIN, coordinator.solar_net.solar_net_device_id),
        )
        self._attr_unique_id = f'{meter_data["serial"]["value"]}-{key}'


class PowerFlowSensor(_FroniusSensorEntity):
    """Defines a Fronius power flow sensor entity."""

    entity_descriptions = POWER_FLOW_ENTITY_DESCRIPTIONS
    _entity_id_prefix = "power_flow_0"

    def __init__(
        self,
        coordinator: FroniusPowerFlowUpdateCoordinator,
        key: str,
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius power flow sensor."""
        super().__init__(coordinator, key, solar_net_id)
        # SolarNet device is already created in FroniusSolarNet._create_solar_net_device
        self._attr_device_info = coordinator.solar_net.system_device_info
        self._attr_unique_id = (
            f"{coordinator.solar_net.solar_net_device_id}-power_flow-{key}"
        )


class StorageSensor(_FroniusSensorEntity):
    """Defines a Fronius storage device sensor entity."""

    entity_descriptions = STORAGE_ENTITY_DESCRIPTIONS

    def __init__(
        self,
        coordinator: FroniusStorageUpdateCoordinator,
        key: str,
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius storage sensor."""
        self._entity_id_prefix = f"storage_{solar_net_id}"
        super().__init__(coordinator, key, solar_net_id)
        storage_data = self._device_data()

        self._attr_unique_id = f'{storage_data["serial"]["value"]}-{key}'
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, storage_data["serial"]["value"])},
            manufacturer=storage_data["manufacturer"]["value"],
            model=storage_data["model"]["value"],
            name=storage_data["model"]["value"],
            via_device=(DOMAIN, coordinator.solar_net.solar_net_device_id),
        )
