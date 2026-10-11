"""Constants for the OpenEVSE integration."""

CONF_SERIAL = "serial"
DOMAIN = "openevse"

CONF_GRID = "grid"
CONF_SOLAR = "solar"
CONF_VOLTAGE = "voltage"
CONF_SHAPER = "shaper"
CONF_VEHICLE_SOC = "vehicle_soc"
CONF_VEHICLE_RANGE = "vehicle_range"
CONF_VEHICLE_ETA = "vehicle_eta"
CONF_HOME_BATTERY_SOC = "home_battery_soc"
CONF_HOME_BATTERY_POWER = "home_battery_power"
CONF_INVERT_GRID = "invert_grid"

SENSOR_FIELDS = (
    CONF_GRID,
    CONF_SOLAR,
    CONF_VOLTAGE,
    CONF_SHAPER,
    CONF_VEHICLE_SOC,
    CONF_VEHICLE_RANGE,
    CONF_VEHICLE_ETA,
    CONF_HOME_BATTERY_SOC,
    CONF_HOME_BATTERY_POWER,
)
