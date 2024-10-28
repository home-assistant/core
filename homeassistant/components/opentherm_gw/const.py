"""Constants for the opentherm_gw integration."""

from dataclasses import dataclass
from enum import StrEnum

from pyotgw import vars as gw_vars

ATTR_GW_ID = "gateway_id"
ATTR_LEVEL = "level"
ATTR_DHW_OVRD = "dhw_override"
ATTR_CH_OVRD = "ch_override"
ATTR_TRANSP_CMD = "transp_cmd"
ATTR_TRANSP_ARG = "transp_arg"

CONF_CLIMATE = "climate"
CONF_FLOOR_TEMP = "floor_temperature"
CONF_PRECISION = "precision"
CONF_READ_PRECISION = "read_precision"
CONF_SET_PRECISION = "set_precision"
CONF_TEMPORARY_OVRD_MODE = "temporary_override_mode"

CONNECTION_TIMEOUT = 10

DATA_GATEWAYS = "gateways"
DATA_OPENTHERM_GW = "opentherm_gw"

DOMAIN = "opentherm_gw"

SERVICE_RESET_GATEWAY = "reset_gateway"
SERVICE_SET_CH_OVRD = "set_central_heating_ovrd"
SERVICE_SET_CLOCK = "set_clock"
SERVICE_SET_CONTROL_SETPOINT = "set_control_setpoint"
SERVICE_SET_HOT_WATER_SETPOINT = "set_hot_water_setpoint"
SERVICE_SET_HOT_WATER_OVRD = "set_hot_water_ovrd"
SERVICE_SET_GPIO_MODE = "set_gpio_mode"
SERVICE_SET_LED_MODE = "set_led_mode"
SERVICE_SET_MAX_MOD = "set_max_modulation"
SERVICE_SET_OAT = "set_outside_temperature"
SERVICE_SET_SB_TEMP = "set_setback_temperature"
SERVICE_SEND_TRANSP_CMD = "send_transparent_command"


class OpenThermDataSource(StrEnum):
    """List valid OpenTherm data sources."""

    BOILER = gw_vars.BOILER
    GATEWAY = gw_vars.OTGW
    THERMOSTAT = gw_vars.THERMOSTAT


class OpenThermDeviceIdentifier(StrEnum):
    """List valid OpenTherm device identifiers."""

    BOILER = "boiler"
    GATEWAY = "gateway"
    THERMOSTAT = "thermostat"


@dataclass(frozen=True, kw_only=True)
class OpenThermDeviceDescription:
    """Describe OpenTherm device properties."""

    data_source: OpenThermDataSource
    device_identifier: OpenThermDeviceIdentifier


BOILER_DEVICE_DESCRIPTION = OpenThermDeviceDescription(
    data_source=OpenThermDataSource.BOILER,
    device_identifier=OpenThermDeviceIdentifier.BOILER,
)
GATEWAY_DEVICE_DESCRIPTION = OpenThermDeviceDescription(
    data_source=OpenThermDataSource.GATEWAY,
    device_identifier=OpenThermDeviceIdentifier.GATEWAY,
)
THERMOSTAT_DEVICE_DESCRIPTION = OpenThermDeviceDescription(
    data_source=OpenThermDataSource.THERMOSTAT,
    device_identifier=OpenThermDeviceIdentifier.THERMOSTAT,
)
