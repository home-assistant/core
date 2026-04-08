"""Constants for the victron_gx integration."""

from victron_mqtt import MetricNature

from homeassistant.components.sensor import SensorStateClass

DOMAIN = "victron_gx"

METRIC_NATURE_TO_STATE_CLASS: dict[MetricNature, SensorStateClass] = {
    MetricNature.MEASUREMENT: SensorStateClass.MEASUREMENT,
    MetricNature.TOTAL: SensorStateClass.TOTAL,
    MetricNature.TOTAL_INCREASING: SensorStateClass.TOTAL_INCREASING,
}

CONF_INSTALLATION_ID = "installation_id"
CONF_MODEL = "model"
CONF_SERIAL = "serial"
