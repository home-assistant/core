"""Constants for the Min/Max integration."""
DOMAIN = "min_max"

ATTR_MIN_VALUE = "min_value"
ATTR_MIN_ENTITY_ID = "min_entity_id"
ATTR_MAX_VALUE = "max_value"
ATTR_MAX_ENTITY_ID = "max_entity_id"
ATTR_COUNT_SENSORS = "count_sensors"
ATTR_MEAN = "mean"
ATTR_MEDIAN = "median"
ATTR_LAST = "last"
ATTR_LAST_ENTITY_ID = "last_entity_id"

ATTR_TO_PROPERTY = [
    ATTR_COUNT_SENSORS,
    ATTR_MAX_VALUE,
    ATTR_MAX_ENTITY_ID,
    ATTR_MEAN,
    ATTR_MEDIAN,
    ATTR_MIN_VALUE,
    ATTR_MIN_ENTITY_ID,
    ATTR_LAST,
    ATTR_LAST_ENTITY_ID,
]

CONF_ENTITY_IDS = "entity_ids"
CONF_ROUND_DIGITS = "round_digits"

ICON = "mdi:calculator"

SENSOR_TYPES = {
    ATTR_MIN_VALUE: "min",
    ATTR_MAX_VALUE: "max",
    ATTR_MEAN: "mean",
    ATTR_MEDIAN: "median",
    ATTR_LAST: "last",
}
