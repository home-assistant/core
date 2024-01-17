"""Constants for the La Marzocco integration."""

from typing import Final

DOMAIN: Final = "lamarzocco"

CONF_CONFIG_ENTRY: Final = "config_entry"
CONF_DAY_OF_WEEK: Final = "day_of_week"
CONF_ENABLE: Final = "enable"
CONF_HOUR_ON: Final = "hour_on"
CONF_HOUR_OFF: Final = "hour_off"
CONF_MACHINE: Final = "machine"
CONF_MINUTE_ON: Final = "minute_on"
CONF_MINUTE_OFF: Final = "minute_off"

SERVICE_AUTO_ON_OFF_ENABLE: Final = "set_auto_on_off_enable"
SERVICE_AUTO_ON_OFF_TIMES: Final = "set_auto_on_off_times"

DAYS: Final = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
