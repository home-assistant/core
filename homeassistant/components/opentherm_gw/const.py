"""Constants for the opentherm_gw integration."""

from dataclasses import dataclass
from enum import StrEnum

from pyotgw import vars as gw_vars

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
