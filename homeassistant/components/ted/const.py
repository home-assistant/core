"""The TED component."""
from homeassistant.const import Platform

DOMAIN = "ted"
PLATFORMS = [Platform.SENSOR]

COORDINATOR = "coordinator"
NAME = "name"

OPTION_DEFAULTS = {
    "spyder_energy_now": False,
    "spyder_energy_daily": False,
    "spyder_energy_mtd": True,
    "mtu_power_voltage": True,
    "mtu_energy_now": False,
    "mtu_energy_daily": False,
    "mtu_energy_mtd": True,
}
