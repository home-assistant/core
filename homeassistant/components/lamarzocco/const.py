"""Constants for the La Marzocco integration."""

from typing import Final

DOMAIN: Final = "lamarzocco"

CONF_CONFIG_ENTRY: Final = "config_entry"
CONF_DAY_OF_WEEK: Final = "day_of_week"
CONF_ENABLE: Final = "enable"
CONF_MACHINE: Final = "machine"
CONF_TIME_ON: Final = "time_on"
CONF_TIME_OFF: Final = "time_off"

SERVICE_AUTO_ON_OFF_ENABLE: Final = "set_auto_on_off_enable"
SERVICE_AUTO_ON_OFF_TIMES: Final = "set_auto_on_off_times"

DAYS: Final = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
