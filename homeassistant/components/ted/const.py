"""The TED component."""
from homeassistant.const import Platform

DOMAIN = "ted"
PLATFORMS = [Platform.SENSOR]

COORDINATOR = "coordinator"
NAME = "name"

CONF_SPYDER_ENERGY_NOW = "spyder_energy_now"
CONF_SPYDER_ENERGY_DAILY = "spyder_energy_daily"
CONF_SPYDER_ENERGY_MTD = "spyder_energy_mtd"
CONF_MTU_POWER_VOLTAGE = "mtu_power_voltage"
CONF_MTU_ENERGY_NOW = "mtu_energy_now"
CONF_MTU_ENERGY_DAILY = "mtu_energy_daily"
CONF_MTU_ENERGY_MTD = "mtu_energy_mtd"

OPTION_DEFAULTS = {
    CONF_SPYDER_ENERGY_NOW: False,
    CONF_SPYDER_ENERGY_DAILY: False,
    CONF_SPYDER_ENERGY_MTD: True,
    CONF_MTU_POWER_VOLTAGE: True,
    CONF_MTU_ENERGY_NOW: False,
    CONF_MTU_ENERGY_DAILY: False,
    CONF_MTU_ENERGY_MTD: True,
}
