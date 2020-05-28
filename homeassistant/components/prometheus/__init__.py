"""Support for Prometheus metrics export."""
import logging
import string

from aiohttp import web
import prometheus_client
import voluptuous as vol

from homeassistant import core as hacore
from homeassistant.components.climate.const import ATTR_CURRENT_TEMPERATURE
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    CONTENT_TYPE_TEXT_PLAIN,
    EVENT_STATE_CHANGED,
    STATE_ON,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    UNIT_PERCENTAGE,
)
from homeassistant.helpers import entityfilter, state as state_helper
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_values import EntityValues
from homeassistant.util.temperature import fahrenheit_to_celsius

_LOGGER = logging.getLogger(__name__)

API_ENDPOINT = "/api/prometheus"

DOMAIN = "prometheus"
CONF_FILTER = "filter"
CONF_PROM_NAMESPACE = "namespace"
CONF_COMPONENT_CONFIG = "component_config"
CONF_COMPONENT_CONFIG_GLOB = "component_config_glob"
CONF_COMPONENT_CONFIG_DOMAIN = "component_config_domain"
CONF_DEFAULT_METRIC = "default_metric"
CONF_OVERRIDE_METRIC = "override_metric"
COMPONENT_CONFIG_SCHEMA_ENTRY = vol.Schema(
    {vol.Optional(CONF_OVERRIDE_METRIC): cv.string}
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            {
                vol.Optional(CONF_FILTER, default={}): entityfilter.FILTER_SCHEMA,
                vol.Optional(CONF_PROM_NAMESPACE): cv.string,
                vol.Optional(CONF_DEFAULT_METRIC): cv.string,
                vol.Optional(CONF_OVERRIDE_METRIC): cv.string,
                vol.Optional(CONF_COMPONENT_CONFIG, default={}): vol.Schema(
                    {cv.entity_id: COMPONENT_CONFIG_SCHEMA_ENTRY}
                ),
                vol.Optional(CONF_COMPONENT_CONFIG_GLOB, default={}): vol.Schema(
                    {cv.string: COMPONENT_CONFIG_SCHEMA_ENTRY}
                ),
                vol.Optional(CONF_COMPONENT_CONFIG_DOMAIN, default={}): vol.Schema(
                    {cv.string: COMPONENT_CONFIG_SCHEMA_ENTRY}
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Activate Prometheus component."""
    hass.http.register_view(PrometheusView(prometheus_client))

    conf = config[DOMAIN]
    entity_filter = conf[CONF_FILTER]
    namespace = conf.get(CONF_PROM_NAMESPACE)
    climate_units = hass.config.units.temperature_unit
    override_metric = conf.get(CONF_OVERRIDE_METRIC)
    default_metric = conf.get(CONF_DEFAULT_METRIC)
    component_config = EntityValues(
        conf[CONF_COMPONENT_CONFIG],
        conf[CONF_COMPONENT_CONFIG_DOMAIN],
        conf[CONF_COMPONENT_CONFIG_GLOB],
    )

    metrics = PrometheusMetrics(
        prometheus_client,
        entity_filter,
        namespace,
        climate_units,
        component_config,
        override_metric,
        default_metric,
    )

    hass.bus.listen(EVENT_STATE_CHANGED, metrics.handle_event)
    return True


class PrometheusMetrics:
    """Model all of the metrics which should be exposed to Prometheus."""

    def __init__(
        self,
        prometheus_cli,
        entity_filter,
        namespace,
        climate_units,
        component_config,
        override_metric,
        default_metric,
    ):
        """Initialize Prometheus Metrics."""
        self.prometheus_cli = prometheus_cli
        self._component_config = component_config
        self._override_metric = override_metric
        self._default_metric = default_metric
        self._filter = entity_filter
        self._sensor_metric_handlers = [
            self._sensor_override_component_metric,
            self._sensor_override_metric,
            self._sensor_attribute_metric,
            self._sensor_default_metric,
            self._sensor_fallback_metric,
        ]

        if namespace:
            self.metrics_prefix = f"{namespace}_"
        else:
            self.metrics_prefix = ""
        self._metrics = {}
        self._climate_units = climate_units

    def handle_event(self, event):
        """Listen for new messages on the bus, and add them to Prometheus."""
        state = event.data.get("new_state")
        if state is None:
            return

        entity_id = state.entity_id
        _LOGGER.debug("Handling state update for %s", entity_id)
        domain, _ = hacore.split_entity_id(entity_id)

        if not self._filter(state.entity_id):
            return

        handler = f"_handle_{domain}"

        if hasattr(self, handler):
            getattr(self, handler)(state)

        metric = self._metric(
            "state_change", self.prometheus_cli.Counter, "The number of state changes"
        )
        metric.labels(**self._labels(state)).inc()

    def _metric(self, metric, factory, documentation, labels=None):
        if labels is None:
            labels = ["entity", "friendly_name", "domain"]

        try:
            return self._metrics[metric]
        except KeyError:
            full_metric_name = self._sanitize_metric_name(
                f"{self.metrics_prefix}{metric}"
            )
            self._metrics[metric] = factory(full_metric_name, documentation, labels)
            return self._metrics[metric]

    @staticmethod
    def _sanitize_metric_name(metric: str) -> str:
        return "".join(
            [
                c
                if c in string.ascii_letters
                or c in string.digits
                or c == "_"
                or c == ":"
                else f"u{hex(ord(c))}"
                for c in metric
            ]
        )

    @staticmethod
    def state_as_number(state):
        """Return a state casted to a float."""
        try:
            value = state_helper.state_as_number(state)
        except ValueError:
            _LOGGER.warning("Could not convert %s to float", state)
            value = 0
        return value

    @staticmethod
    def _labels(state):
        return {
            "entity": state.entity_id,
            "domain": state.domain,
            "friendly_name": state.attributes.get("friendly_name"),
        }

    def _battery(self, state):
        if "battery_level" in state.attributes:
            metric = self._metric(
                "battery_level_percent",
                self.prometheus_cli.Gauge,
                "Battery level as a percentage of its capacity",
            )
            try:
                value = float(state.attributes["battery_level"])
                metric.labels(**self._labels(state)).set(value)
            except ValueError:
                pass

    def _handle_binary_sensor(self, state):
        metric = self._metric(
            "binary_sensor_state",
            self.prometheus_cli.Gauge,
            "State of the binary sensor (0/1)",
        )
        value = self.state_as_number(state)
        metric.labels(**self._labels(state)).set(value)

    def _handle_input_boolean(self, state):
        metric = self._metric(
            "input_boolean_state",
            self.prometheus_cli.Gauge,
            "State of the input boolean (0/1)",
        )
        value = self.state_as_number(state)
        metric.labels(**self._labels(state)).set(value)

    def _handle_device_tracker(self, state):
        metric = self._metric(
            "device_tracker_state",
            self.prometheus_cli.Gauge,
            "State of the device tracker (0/1)",
        )
        value = self.state_as_number(state)
        metric.labels(**self._labels(state)).set(value)

    def _handle_person(self, state):
        metric = self._metric(
            "person_state", self.prometheus_cli.Gauge, "State of the person (0/1)"
        )
        value = self.state_as_number(state)
        metric.labels(**self._labels(state)).set(value)

    def _handle_light(self, state):
        metric = self._metric(
            "light_state", self.prometheus_cli.Gauge, "Load level of a light (0..1)"
        )

        try:
            if "brightness" in state.attributes and state.state == STATE_ON:
                value = state.attributes["brightness"] / 255.0
            else:
                value = self.state_as_number(state)
            value = value * 100
            metric.labels(**self._labels(state)).set(value)
        except ValueError:
            pass

    def _handle_lock(self, state):
        metric = self._metric(
            "lock_state", self.prometheus_cli.Gauge, "State of the lock (0/1)"
        )
        value = self.state_as_number(state)
        metric.labels(**self._labels(state)).set(value)

    def _handle_climate(self, state):
        temp = state.attributes.get(ATTR_TEMPERATURE)
        if temp:
            if self._climate_units == TEMP_FAHRENHEIT:
                temp = fahrenheit_to_celsius(temp)
            metric = self._metric(
                "temperature_c",
                self.prometheus_cli.Gauge,
                "Temperature in degrees Celsius",
            )
            metric.labels(**self._labels(state)).set(temp)

        current_temp = state.attributes.get(ATTR_CURRENT_TEMPERATURE)
        if current_temp:
            if self._climate_units == TEMP_FAHRENHEIT:
                current_temp = fahrenheit_to_celsius(current_temp)
            metric = self._metric(
                "current_temperature_c",
                self.prometheus_cli.Gauge,
                "Current Temperature in degrees Celsius",
            )
            metric.labels(**self._labels(state)).set(current_temp)

    def _handle_sensor(self, state):
        unit = self._unit_string(state.attributes.get(ATTR_UNIT_OF_MEASUREMENT))

        for metric_handler in self._sensor_metric_handlers:
            metric = metric_handler(state, unit)
            if metric is not None:
                break

        if metric is not None:
            _metric = self._metric(
                metric, self.prometheus_cli.Gauge, f"Sensor data measured in {unit}"
            )

            try:
                value = self.state_as_number(state)
                if unit == TEMP_FAHRENHEIT:
                    value = fahrenheit_to_celsius(value)
                _metric.labels(**self._labels(state)).set(value)
            except ValueError:
                pass

        self._battery(state)

    def _sensor_default_metric(self, state, unit):
        """Get default metric."""
        return self._default_metric

    @staticmethod
    def _sensor_attribute_metric(state, unit):
        """Get metric based on device class attribute."""
        metric = state.attributes.get(ATTR_DEVICE_CLASS)
        if metric is not None:
            return f"{metric}_{unit}"
        return None

    def _sensor_override_metric(self, state, unit):
        """Get metric from override in configuration."""
        if self._override_metric:
            return self._override_metric
        return None

    def _sensor_override_component_metric(self, state, unit):
        """Get metric from override in component confioguration."""
        return self._component_config.get(state.entity_id).get(CONF_OVERRIDE_METRIC)

    @staticmethod
    def _sensor_fallback_metric(state, unit):
        """Get metric from fallback logic for compatibility."""
        if unit in (None, ""):
            _LOGGER.debug("Unsupported sensor: %s", state.entity_id)
            return None
        return f"sensor_unit_{unit}"

    @staticmethod
    def _unit_string(unit):
        """Get a formatted string of the unit."""
        if unit is None:
            return

        units = {
            TEMP_CELSIUS: "c",
            TEMP_FAHRENHEIT: "c",  # F should go into C metric
            UNIT_PERCENTAGE: "percent",
        }
        default = unit.replace("/", "_per_")
        default = default.lower()
        return units.get(unit, default)

    def _handle_switch(self, state):
        metric = self._metric(
            "switch_state", self.prometheus_cli.Gauge, "State of the switch (0/1)"
        )

        try:
            value = self.state_as_number(state)
            metric.labels(**self._labels(state)).set(value)
        except ValueError:
            pass

    def _handle_zwave(self, state):
        self._battery(state)

    def _handle_automation(self, state):
        metric = self._metric(
            "automation_triggered_count",
            self.prometheus_cli.Counter,
            "Count of times an automation has been triggered",
        )

        metric.labels(**self._labels(state)).inc()


class PrometheusView(HomeAssistantView):
    """Handle Prometheus requests."""

    url = API_ENDPOINT
    name = "api:prometheus"

    def __init__(self, prometheus_cli):
        """Initialize Prometheus view."""
        self.prometheus_cli = prometheus_cli

    async def get(self, request):
        """Handle request for Prometheus metrics."""
        _LOGGER.debug("Received Prometheus metrics request")

        return web.Response(
            body=self.prometheus_cli.generate_latest(),
            content_type=CONTENT_TYPE_TEXT_PLAIN,
        )
