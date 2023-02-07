"""Support for Prometheus metrics export."""
from contextlib import suppress
import logging
import string

from aiohttp import web
import prometheus_client
import voluptuous as vol

from homeassistant import core as hacore
from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODES,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    HVACAction,
)
from homeassistant.components.cover import ATTR_POSITION, ATTR_TILT_POSITION
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.humidifier import ATTR_AVAILABLE_MODES, ATTR_HUMIDITY
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_MODE,
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    CONTENT_TYPE_TEXT_PLAIN,
    EVENT_STATE_CHANGED,
    PERCENTAGE,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_ON,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entityfilter, state as state_helper
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_registry import EVENT_ENTITY_REGISTRY_UPDATED
from homeassistant.helpers.entity_values import EntityValues
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.unit_conversion import TemperatureConverter

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

DEFAULT_NAMESPACE = "homeassistant"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            {
                vol.Optional(CONF_FILTER, default={}): entityfilter.FILTER_SCHEMA,
                vol.Optional(CONF_PROM_NAMESPACE, default=DEFAULT_NAMESPACE): cv.string,
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


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
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

    hass.bus.listen(EVENT_STATE_CHANGED, metrics.handle_state_changed)
    hass.bus.listen(
        EVENT_ENTITY_REGISTRY_UPDATED, metrics.handle_entity_registry_updated
    )
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

    def handle_state_changed(self, event):
        """Listen for new messages on the bus, and add them to Prometheus."""
        if (state := event.data.get("new_state")) is None:
            return

        entity_id = state.entity_id
        _LOGGER.debug("Handling state update for %s", entity_id)
        domain, _ = hacore.split_entity_id(entity_id)

        if not self._filter(state.entity_id):
            return

        if (old_state := event.data.get("old_state")) is not None and (
            old_friendly_name := old_state.attributes.get(ATTR_FRIENDLY_NAME)
        ) != state.attributes.get(ATTR_FRIENDLY_NAME):
            self._remove_labelsets(old_state.entity_id, old_friendly_name)

        ignored_states = (STATE_UNAVAILABLE, STATE_UNKNOWN)

        handler = f"_handle_{domain}"

        if hasattr(self, handler) and state.state not in ignored_states:
            getattr(self, handler)(state)

        labels = self._labels(state)
        state_change = self._metric(
            "state_change", self.prometheus_cli.Counter, "The number of state changes"
        )
        state_change.labels(**labels).inc()

        entity_available = self._metric(
            "entity_available",
            self.prometheus_cli.Gauge,
            "Entity is available (not in the unavailable or unknown state)",
        )
        entity_available.labels(**labels).set(float(state.state not in ignored_states))

        last_updated_time_seconds = self._metric(
            "last_updated_time_seconds",
            self.prometheus_cli.Gauge,
            "The last_updated timestamp",
        )
        last_updated_time_seconds.labels(**labels).set(state.last_updated.timestamp())

    def handle_entity_registry_updated(self, event):
        """Listen for deleted, disabled or renamed entities and remove them from the Prometheus Registry."""
        if (action := event.data.get("action")) in (None, "create"):
            return

        entity_id = event.data.get("entity_id")
        _LOGGER.debug("Handling entity update for %s", entity_id)

        metrics_entity_id = None

        if action == "remove":
            metrics_entity_id = entity_id
        elif action == "update":
            changes = event.data.get("changes")

            if "entity_id" in changes:
                metrics_entity_id = changes["entity_id"]
            elif "disabled_by" in changes:
                metrics_entity_id = entity_id

        if metrics_entity_id:
            self._remove_labelsets(metrics_entity_id)

    def _remove_labelsets(self, entity_id, friendly_name=None):
        """Remove labelsets matching the given entity id from all metrics."""
        for _, metric in self._metrics.items():
            for sample in metric.collect()[0].samples:
                if sample.labels["entity"] == entity_id and (
                    not friendly_name or sample.labels["friendly_name"] == friendly_name
                ):
                    _LOGGER.debug(
                        "Removing labelset from %s for entity_id: %s",
                        sample.name,
                        entity_id,
                    )
                    with suppress(KeyError):
                        metric.remove(*sample.labels.values())

    def _handle_attributes(self, state):
        for key, value in state.attributes.items():
            metric = self._metric(
                f"{state.domain}_attr_{key.lower()}",
                self.prometheus_cli.Gauge,
                f"{key} attribute of {state.domain} entity",
            )

            try:
                value = float(value)
                metric.labels(**self._labels(state)).set(value)
            except (ValueError, TypeError):
                pass

    def _metric(self, metric, factory, documentation, extra_labels=None):
        labels = ["entity", "friendly_name", "domain"]
        if extra_labels is not None:
            labels.extend(extra_labels)

        try:
            return self._metrics[metric]
        except KeyError:
            full_metric_name = self._sanitize_metric_name(
                f"{self.metrics_prefix}{metric}"
            )
            self._metrics[metric] = factory(
                full_metric_name,
                documentation,
                labels,
                registry=self.prometheus_cli.REGISTRY,
            )
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
            _LOGGER.debug("Could not convert %s to float", state)
            value = 0
        return value

    @staticmethod
    def _labels(state):
        return {
            "entity": state.entity_id,
            "domain": state.domain,
            "friendly_name": state.attributes.get(ATTR_FRIENDLY_NAME),
        }

    def _battery(self, state):
        if "battery_level" in state.attributes:
            metric = self._metric(
                "battery_level_percent",
                self.prometheus_cli.Gauge,
                "Battery level as a percentage of its capacity",
            )
            try:
                value = float(state.attributes[ATTR_BATTERY_LEVEL])
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

    def _handle_input_number(self, state):
        if unit := self._unit_string(state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)):
            metric = self._metric(
                f"input_number_state_{unit}",
                self.prometheus_cli.Gauge,
                f"State of the input number measured in {unit}",
            )
        else:
            metric = self._metric(
                "input_number_state",
                self.prometheus_cli.Gauge,
                "State of the input number",
            )

        with suppress(ValueError):
            value = self.state_as_number(state)
            if (
                state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
                == UnitOfTemperature.FAHRENHEIT
            ):
                value = TemperatureConverter.convert(
                    value, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS
                )
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

    def _handle_cover(self, state):
        metric = self._metric(
            "cover_state",
            self.prometheus_cli.Gauge,
            "State of the cover (0/1)",
            ["state"],
        )

        cover_states = [STATE_CLOSED, STATE_CLOSING, STATE_OPEN, STATE_OPENING]
        for cover_state in cover_states:
            metric.labels(**dict(self._labels(state), state=cover_state)).set(
                float(cover_state == state.state)
            )

        position = state.attributes.get(ATTR_POSITION)
        if position is not None:
            position_metric = self._metric(
                "cover_position",
                self.prometheus_cli.Gauge,
                "Position of the cover (0-100)",
            )
            position_metric.labels(**self._labels(state)).set(float(position))

        tilt_position = state.attributes.get(ATTR_TILT_POSITION)
        if tilt_position is not None:
            tilt_position_metric = self._metric(
                "cover_tilt_position",
                self.prometheus_cli.Gauge,
                "Tilt Position of the cover (0-100)",
            )
            tilt_position_metric.labels(**self._labels(state)).set(float(tilt_position))

    def _handle_light(self, state):
        metric = self._metric(
            "light_brightness_percent",
            self.prometheus_cli.Gauge,
            "Light brightness percentage (0..100)",
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

    def _handle_climate_temp(self, state, attr, metric_name, metric_description):
        if (temp := state.attributes.get(attr)) is not None:
            if self._climate_units == UnitOfTemperature.FAHRENHEIT:
                temp = TemperatureConverter.convert(
                    temp, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS
                )
            metric = self._metric(
                metric_name,
                self.prometheus_cli.Gauge,
                metric_description,
            )
            metric.labels(**self._labels(state)).set(temp)

    def _handle_climate(self, state):
        self._handle_climate_temp(
            state,
            ATTR_TEMPERATURE,
            "climate_target_temperature_celsius",
            "Target temperature in degrees Celsius",
        )
        self._handle_climate_temp(
            state,
            ATTR_TARGET_TEMP_HIGH,
            "climate_target_temperature_high_celsius",
            "Target high temperature in degrees Celsius",
        )
        self._handle_climate_temp(
            state,
            ATTR_TARGET_TEMP_LOW,
            "climate_target_temperature_low_celsius",
            "Target low temperature in degrees Celsius",
        )
        self._handle_climate_temp(
            state,
            ATTR_CURRENT_TEMPERATURE,
            "climate_current_temperature_celsius",
            "Current temperature in degrees Celsius",
        )

        if current_action := state.attributes.get(ATTR_HVAC_ACTION):
            metric = self._metric(
                "climate_action",
                self.prometheus_cli.Gauge,
                "HVAC action",
                ["action"],
            )
            for action in HVACAction:
                metric.labels(**dict(self._labels(state), action=action.value)).set(
                    float(action == current_action)
                )

        current_mode = state.state
        available_modes = state.attributes.get(ATTR_HVAC_MODES)
        if current_mode and available_modes:
            metric = self._metric(
                "climate_mode",
                self.prometheus_cli.Gauge,
                "HVAC mode",
                ["mode"],
            )
            for mode in available_modes:
                metric.labels(**dict(self._labels(state), mode=mode)).set(
                    float(mode == current_mode)
                )

    def _handle_humidifier(self, state):
        humidifier_target_humidity_percent = state.attributes.get(ATTR_HUMIDITY)
        if humidifier_target_humidity_percent:
            metric = self._metric(
                "humidifier_target_humidity_percent",
                self.prometheus_cli.Gauge,
                "Target Relative Humidity",
            )
            metric.labels(**self._labels(state)).set(humidifier_target_humidity_percent)

        metric = self._metric(
            "humidifier_state",
            self.prometheus_cli.Gauge,
            "State of the humidifier (0/1)",
        )
        try:
            value = self.state_as_number(state)
            metric.labels(**self._labels(state)).set(value)
        except ValueError:
            pass

        current_mode = state.attributes.get(ATTR_MODE)
        available_modes = state.attributes.get(ATTR_AVAILABLE_MODES)
        if current_mode and available_modes:
            metric = self._metric(
                "humidifier_mode",
                self.prometheus_cli.Gauge,
                "Humidifier Mode",
                ["mode"],
            )
            for mode in available_modes:
                metric.labels(**dict(self._labels(state), mode=mode)).set(
                    float(mode == current_mode)
                )

    def _handle_sensor(self, state):
        unit = self._unit_string(state.attributes.get(ATTR_UNIT_OF_MEASUREMENT))

        for metric_handler in self._sensor_metric_handlers:
            metric = metric_handler(state, unit)
            if metric is not None:
                break

        if metric is not None:
            documentation = "State of the sensor"
            if unit:
                documentation = f"Sensor data measured in {unit}"

            _metric = self._metric(metric, self.prometheus_cli.Gauge, documentation)

            try:
                value = self.state_as_number(state)
                if (
                    state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
                    == UnitOfTemperature.FAHRENHEIT
                ):
                    value = TemperatureConverter.convert(
                        value, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS
                    )
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
            return f"sensor_{metric}_{unit}"
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
            try:
                state_helper.state_as_number(state)
            except ValueError:
                _LOGGER.debug("Unsupported sensor: %s", state.entity_id)
                return None
            return "sensor_state"
        return f"sensor_unit_{unit}"

    @staticmethod
    def _unit_string(unit):
        """Get a formatted string of the unit."""
        if unit is None:
            return

        units = {
            UnitOfTemperature.CELSIUS: "celsius",
            UnitOfTemperature.FAHRENHEIT: "celsius",  # F should go into C metric
            PERCENTAGE: "percent",
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

        self._handle_attributes(state)

    def _handle_zwave(self, state):
        self._battery(state)

    def _handle_automation(self, state):
        metric = self._metric(
            "automation_triggered_count",
            self.prometheus_cli.Counter,
            "Count of times an automation has been triggered",
        )

        metric.labels(**self._labels(state)).inc()

    def _handle_counter(self, state):
        metric = self._metric(
            "counter_value",
            self.prometheus_cli.Gauge,
            "Value of counter entities",
        )

        metric.labels(**self._labels(state)).set(self.state_as_number(state))


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
            body=self.prometheus_cli.generate_latest(self.prometheus_cli.REGISTRY),
            content_type=CONTENT_TYPE_TEXT_PLAIN,
        )
