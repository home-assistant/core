"""Support for OpenTherm Gateway binary sensors."""

from dataclasses import dataclass

from pyotgw import vars as gw_vars

from homeassistant.components.binary_sensor import (
    ENTITY_ID_FORMAT,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OpenThermGatewayHub
from .const import DATA_GATEWAYS, DATA_OPENTHERM_GW
from .entity import OpenThermEntity, OpenThermEntityDescription


@dataclass(frozen=True, kw_only=True)
class OpenThermBinarySensorEntityDescription(
    BinarySensorEntityDescription, OpenThermEntityDescription
):
    """Describes opentherm_gw binary sensor entity."""


BINARY_SENSOR_INFO: tuple[
    tuple[list[str], OpenThermBinarySensorEntityDescription], ...
] = (
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.DATA_MASTER_CH_ENABLED,
            friendly_name_format="Thermostat Central Heating {}",
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.DATA_MASTER_DHW_ENABLED,
            friendly_name_format="Thermostat Hot Water {}",
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.DATA_MASTER_COOLING_ENABLED,
            friendly_name_format="Thermostat Cooling {}",
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.DATA_MASTER_OTC_ENABLED,
            friendly_name_format="Thermostat Outside Temperature Correction {}",
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.DATA_MASTER_CH2_ENABLED,
            friendly_name_format="Thermostat Central Heating 2 {}",
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.DATA_SLAVE_FAULT_IND,
            friendly_name_format="Boiler Fault {}",
            device_class=BinarySensorDeviceClass.PROBLEM,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.DATA_SLAVE_CH_ACTIVE,
            friendly_name_format="Boiler Central Heating {}",
            device_class=BinarySensorDeviceClass.HEAT,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.DATA_SLAVE_DHW_ACTIVE,
            friendly_name_format="Boiler Hot Water {}",
            device_class=BinarySensorDeviceClass.HEAT,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.DATA_SLAVE_FLAME_ON,
            friendly_name_format="Boiler Flame {}",
            device_class=BinarySensorDeviceClass.HEAT,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.DATA_SLAVE_COOLING_ACTIVE,
            friendly_name_format="Boiler Cooling {}",
            device_class=BinarySensorDeviceClass.COLD,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.DATA_SLAVE_CH2_ACTIVE,
            friendly_name_format="Boiler Central Heating 2 {}",
            device_class=BinarySensorDeviceClass.HEAT,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.DATA_SLAVE_DIAG_IND,
            friendly_name_format="Boiler Diagnostics {}",
            device_class=BinarySensorDeviceClass.PROBLEM,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.DATA_SLAVE_DHW_PRESENT,
            friendly_name_format="Boiler Hot Water Present {}",
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.DATA_SLAVE_CONTROL_TYPE,
            friendly_name_format="Boiler Control Type {}",
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.DATA_SLAVE_COOLING_SUPPORTED,
            friendly_name_format="Boiler Cooling Support {}",
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.DATA_SLAVE_DHW_CONFIG,
            friendly_name_format="Boiler Hot Water Configuration {}",
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.DATA_SLAVE_MASTER_LOW_OFF_PUMP,
            friendly_name_format="Boiler Pump Commands Support {}",
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.DATA_SLAVE_CH2_PRESENT,
            friendly_name_format="Boiler Central Heating 2 Present {}",
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.DATA_SLAVE_SERVICE_REQ,
            friendly_name_format="Boiler Service Required {}",
            device_class=BinarySensorDeviceClass.PROBLEM,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.DATA_SLAVE_REMOTE_RESET,
            friendly_name_format="Boiler Remote Reset Support {}",
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.DATA_SLAVE_LOW_WATER_PRESS,
            friendly_name_format="Boiler Low Water Pressure {}",
            device_class=BinarySensorDeviceClass.PROBLEM,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.DATA_SLAVE_GAS_FAULT,
            friendly_name_format="Boiler Gas Fault {}",
            device_class=BinarySensorDeviceClass.PROBLEM,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.DATA_SLAVE_AIR_PRESS_FAULT,
            friendly_name_format="Boiler Air Pressure Fault {}",
            device_class=BinarySensorDeviceClass.PROBLEM,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.DATA_SLAVE_WATER_OVERTEMP,
            friendly_name_format="Boiler Water Overtemperature {}",
            device_class=BinarySensorDeviceClass.PROBLEM,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.DATA_REMOTE_TRANSFER_DHW,
            friendly_name_format="Remote Hot Water Setpoint Transfer Support {}",
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.DATA_REMOTE_TRANSFER_MAX_CH,
            friendly_name_format="Remote Maximum Central Heating Setpoint Write Support {}",
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.DATA_REMOTE_RW_DHW,
            friendly_name_format="Remote Hot Water Setpoint Write Support {}",
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.DATA_REMOTE_RW_MAX_CH,
            friendly_name_format="Remote Central Heating Setpoint Write Support {}",
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.DATA_ROVRD_MAN_PRIO,
            friendly_name_format="Remote Override Manual Change Priority {}",
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.DATA_ROVRD_AUTO_PRIO,
            friendly_name_format="Remote Override Program Change Priority {}",
        ),
    ),
    (
        [gw_vars.OTGW],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.OTGW_GPIO_A_STATE,
            friendly_name_format="Gateway GPIO A {}",
        ),
    ),
    (
        [gw_vars.OTGW],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.OTGW_GPIO_B_STATE,
            friendly_name_format="Gateway GPIO B {}",
        ),
    ),
    (
        [gw_vars.OTGW],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.OTGW_IGNORE_TRANSITIONS,
            friendly_name_format="Gateway Ignore Transitions {}",
        ),
    ),
    (
        [gw_vars.OTGW],
        OpenThermBinarySensorEntityDescription(
            key=gw_vars.OTGW_OVRD_HB,
            friendly_name_format="Gateway Override High Byte {}",
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the OpenTherm Gateway binary sensors."""
    gw_hub = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][config_entry.data[CONF_ID]]

    async_add_entities(
        OpenThermBinarySensor(gw_hub, source, description)
        for sources, description in BINARY_SENSOR_INFO
        for source in sources
    )


class OpenThermBinarySensor(OpenThermEntity, BinarySensorEntity):
    """Represent an OpenTherm Gateway binary sensor."""

    entity_description: OpenThermBinarySensorEntityDescription

    def __init__(
        self,
        gw_hub: OpenThermGatewayHub,
        source: str,
        description: OpenThermBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{description.key}_{source}_{gw_hub.hub_id}",
            hass=gw_hub.hass,
        )
        super().__init__(gw_hub, source, description)

    @callback
    def receive_report(self, status: dict[str, dict]) -> None:
        """Handle status updates from the component."""
        self._attr_available = self._gateway.connected
        state = status[self._source].get(self.entity_description.key)
        self._attr_is_on = None if state is None else bool(state)
        self.async_write_ha_state()
