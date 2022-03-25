"""Constants for the Time & Date integration."""

DOMAIN = "time_date"

CONF_DISPLAY_OPTION = "display_option"

CONF_BEAT = "beat"
CONF_DATE = "date"
CONF_DATE_TIME = "date_time"
CONF_DATE_TIME_ISO = "date_time_iso"
CONF_DATE_TIME_UTC = "date_time_utc"
CONF_TIME = "time"
CONF_TIME_DATE = "time_date"
CONF_TIME_UTC = "time_utc"

OPTION_TYPES = {
    CONF_TIME: "Time",
    CONF_DATE: "Date",
    CONF_DATE_TIME: "Date & Time",
    CONF_DATE_TIME_UTC: "Date & Time (UTC)",
    CONF_DATE_TIME_ISO: "Date & Time (ISO)",
    CONF_TIME_DATE: "Time & Date",
    CONF_BEAT: "Internet Time",
    CONF_TIME_UTC: "Time (UTC)",
}
