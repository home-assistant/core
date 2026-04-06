"""Constants for the victron_gx integration."""

from victron_mqtt import MetricNature

from homeassistant.components.sensor import SensorStateClass

DOMAIN = "victron_gx"

CONF_INSTALLATION_ID = "installation_id"
CONF_MODEL = "model"
CONF_SERIAL = "serial"

# Not using GenericOnOff as some switches use different enums.
# It has to be with id "on" to be on and "off" to be off.
SWITCH_ON_ID = "on"
SWITCH_OFF_ID = "off"

METRIC_NATURE_TO_STATE_CLASS: dict[MetricNature, SensorStateClass] = {
    MetricNature.MEASUREMENT: SensorStateClass.MEASUREMENT,
    MetricNature.TOTAL: SensorStateClass.TOTAL,
    MetricNature.TOTAL_INCREASING: SensorStateClass.TOTAL_INCREASING,
}
