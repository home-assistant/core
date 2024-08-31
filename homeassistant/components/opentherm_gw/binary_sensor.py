"""Support for OpenTherm Gateway binary sensors."""

from dataclasses import dataclass

from pyotgw import vars as gw_vars

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_GATEWAYS, DATA_OPENTHERM_GW
from .entity import (
    OpenThermBaseEntity,
    OpenThermBoilerDeviceEntity,
    OpenThermEntityDescription,
    OpenThermGatewayDeviceEntity,
    OpenThermThermostatDeviceEntity,
)


@dataclass(frozen=True, kw_only=True)
class OpenThermBinarySensorEntityDescription(
    OpenThermEntityDescription, BinarySensorEntityDescription
):
    """Describes opentherm_gw binary sensor entity."""

    entity_category = EntityCategory.DIAGNOSTIC


BOILER_BINARY_SENSOR_DESCRIPTIONS: tuple[
    OpenThermBinarySensorEntityDescription, ...
] = (
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.DATA_SLAVE_FAULT_IND,
        translation_key="fault_indication",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.DATA_SLAVE_CH_ACTIVE,
        translation_key="central_heating_n",
        translation_placeholders={"circuit_number": "1"},
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.DATA_SLAVE_DHW_ACTIVE,
        translation_key="hot_water",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.DATA_SLAVE_FLAME_ON,
        translation_key="flame",
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.DATA_SLAVE_COOLING_ACTIVE,
        translation_key="cooling",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.DATA_SLAVE_CH2_ACTIVE,
        translation_key="central_heating_n",
        translation_placeholders={"circuit_number": "2"},
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.DATA_SLAVE_DIAG_IND,
        translation_key="diagnostic_indication",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.DATA_SLAVE_DHW_PRESENT,
        translation_key="supports_hot_water",
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.DATA_SLAVE_CONTROL_TYPE,
        translation_key="control_type",
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.DATA_SLAVE_COOLING_SUPPORTED,
        translation_key="supports_cooling",
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.DATA_SLAVE_DHW_CONFIG,
        translation_key="hot_water_config",
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.DATA_SLAVE_MASTER_LOW_OFF_PUMP,
        translation_key="supports_pump_control",
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.DATA_SLAVE_CH2_PRESENT,
        translation_key="supports_ch_2",
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.DATA_SLAVE_SERVICE_REQ,
        translation_key="service_required",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.DATA_SLAVE_REMOTE_RESET,
        translation_key="supports_remote_reset",
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.DATA_SLAVE_LOW_WATER_PRESS,
        translation_key="low_water_pressure",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.DATA_SLAVE_GAS_FAULT,
        translation_key="gas_fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.DATA_SLAVE_AIR_PRESS_FAULT,
        translation_key="air_pressure_fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.DATA_SLAVE_WATER_OVERTEMP,
        translation_key="water_overtemperature",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.DATA_REMOTE_TRANSFER_MAX_CH,
        translation_key="supports_central_heating_setpoint_transfer",
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.DATA_REMOTE_RW_MAX_CH,
        translation_key="supports_central_heating_setpoint_writing",
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.DATA_REMOTE_TRANSFER_DHW,
        translation_key="supports_hot_water_setpoint_transfer",
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.DATA_REMOTE_RW_DHW,
        translation_key="supports_hot_water_setpoint_writing",
    ),
)

GATEWAY_BINARY_SENSOR_DESCRIPTIONS: tuple[
    OpenThermBinarySensorEntityDescription, ...
] = (
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.OTGW_GPIO_A_STATE,
        translation_key="gpio_state_n",
        translation_placeholders={"gpio_id": "A"},
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.OTGW_GPIO_B_STATE,
        translation_key="gpio_state_n",
        translation_placeholders={"gpio_id": "B"},
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.OTGW_IGNORE_TRANSITIONS,
        translation_key="ignore_transitions",
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.OTGW_OVRD_HB,
        translation_key="override_high_byte",
    ),
)

THERMOSTAT_BINARY_SENSOR_DESCRIPTIONS: tuple[
    OpenThermBinarySensorEntityDescription, ...
] = (
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.DATA_MASTER_CH_ENABLED,
        translation_key="central_heating_n",
        translation_placeholders={"circuit_number": "1"},
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.DATA_MASTER_DHW_ENABLED,
        translation_key="hot_water",
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.DATA_MASTER_COOLING_ENABLED,
        translation_key="cooling",
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.DATA_MASTER_OTC_ENABLED,
        translation_key="outside_temp_correction",
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.DATA_MASTER_CH2_ENABLED,
        translation_key="central_heating_n",
        translation_placeholders={"circuit_number": "2"},
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.DATA_ROVRD_MAN_PRIO,
        translation_key="override_manual_change_prio",
    ),
    OpenThermBinarySensorEntityDescription(
        key=gw_vars.DATA_ROVRD_AUTO_PRIO,
        translation_key="override_program_change_prio",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the OpenTherm Gateway binary sensors."""
    gw_hub = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][config_entry.data[CONF_ID]]

    for klass, descriptions in (
        (OpenThermBoilerBinarySensorEntity, BOILER_BINARY_SENSOR_DESCRIPTIONS),
        (OpenThermGatewayBinarySensorEntity, GATEWAY_BINARY_SENSOR_DESCRIPTIONS),
        (OpenThermThermostatBinarySensorEntity, THERMOSTAT_BINARY_SENSOR_DESCRIPTIONS),
    ):
        async_add_entities(klass(gw_hub, description) for description in descriptions)


class OpenThermBinarySensor(OpenThermBaseEntity, BinarySensorEntity):
    """Represent an OpenTherm Gateway binary sensor."""

    entity_description: OpenThermBinarySensorEntityDescription

    @callback
    def receive_report(self, status: dict[str, dict]) -> None:
        """Handle status updates from the component."""
        state = status[self._data_source].get(self.entity_description.key)
        self._attr_is_on = None if state is None else bool(state)
        self.async_write_ha_state()


class OpenThermBoilerBinarySensorEntity(
    OpenThermBinarySensor, OpenThermBoilerDeviceEntity
):
    """Represent an OpenTherm binary sensor on the Boiler."""

    entity_description: OpenThermBinarySensorEntityDescription


class OpenThermGatewayBinarySensorEntity(
    OpenThermBinarySensor, OpenThermGatewayDeviceEntity
):
    """Represent an OpenTherm binary sensor on the Gateway."""

    entity_description: OpenThermBinarySensorEntityDescription


class OpenThermThermostatBinarySensorEntity(
    OpenThermBinarySensor, OpenThermThermostatDeviceEntity
):
    """Represent an OpenTherm binary sensor on the Thermostat."""

    entity_description: OpenThermBinarySensorEntityDescription
