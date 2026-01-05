"""Support for Prometheus metrics export."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import astuple, dataclass
import logging
import string
from typing import Any, cast

from aiohttp import web
import prometheus_client
from prometheus_client.metrics import MetricWrapperBase
import voluptuous as vol

from homeassistant import core as hacore
from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODES,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    HVACAction,
)
from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
)
from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
)
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.components.humidifier import ATTR_AVAILABLE_MODES, ATTR_HUMIDITY
from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.components.sensor import SensorDeviceClass

# Alias water_heater constants to avoid name clashes with similarly named climate constants
from homeassistant.components.water_heater import (
    ATTR_AWAY_MODE as WATER_HEATER_ATTR_AWAY_MODE,
    ATTR_CURRENT_TEMPERATURE as WATER_HEATER_ATTR_CURRENT_TEMPERATURE,
    ATTR_MAX_TEMP as WATER_HEATER_ATTR_MAX_TEMP,
    ATTR_MIN_TEMP as WATER_HEATER_ATTR_MIN_TEMP,
    ATTR_OPERATION_LIST as WATER_HEATER_ATTR_OPERATION_LIST,
    ATTR_OPERATION_MODE as WATER_HEATER_ATTR_OPERATION_MODE,
    ATTR_TARGET_TEMP_HIGH as WATER_HEATER_ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW as WATER_HEATER_ATTR_TARGET_TEMP_LOW,
)
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
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    entityfilter,
    floor_registry as fr,
    state as state_helper,
)
from homeassistant.helpers.area_registry import (
    EVENT_AREA_REGISTRY_UPDATED,
    AreaEntry,
    EventAreaRegistryUpdatedData,
)
from homeassistant.helpers.device_registry import (
    EVENT_DEVICE_REGISTRY_UPDATED,
    EventDeviceRegistryUpdatedData,
)
from homeassistant.helpers.entity_registry import (
    EVENT_ENTITY_REGISTRY_UPDATED,
    EventEntityRegistryUpdatedData,
)
from homeassistant.helpers.entity_values import EntityValues
from homeassistant.helpers.floor_registry import (
    EVENT_FLOOR_REGISTRY_UPDATED,
    EventFloorRegistryUpdatedData,
    FloorEntry,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.dt import as_timestamp
from homeassistant.util.unit_conversion import TemperatureConverter

_LOGGER = logging.getLogger(__name__)

API_ENDPOINT = "/api/prometheus"
IGNORED_STATES = frozenset({STATE_UNAVAILABLE, STATE_UNKNOWN})


DOMAIN = "prometheus"
CONF_FILTER = "filter"
CONF_REQUIRES_AUTH = "requires_auth"
CONF_PROM_NAMESPACE = "namespace"
CONF_COMPONENT_CONFIG = "component_config"
CONF_COMPONENT_CONFIG_GLOB = "component_config_glob"
CONF_COMPONENT_CONFIG_DOMAIN = "component_config_domain"
CONF_DEFAULT_METRIC = "default_metric"
CONF_OVERRIDE_METRIC = "override_metric"
COMPONENT_CONFIG_SCHEMA_ENTRY = vol.Schema(
    {vol.Optional(CONF_OVERRIDE_METRIC): cv.string}
)
ALLOWED_METRIC_CHARS = set(string.ascii_letters + string.digits + "_:")

DEFAULT_NAMESPACE = "homeassistant"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            {
                vol.Optional(CONF_FILTER, default={}): entityfilter.FILTER_SCHEMA,
                vol.Optional(CONF_PROM_NAMESPACE, default=DEFAULT_NAMESPACE): cv.string,
                vol.Optional(CONF_REQUIRES_AUTH, default=True): cv.boolean,
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
    hass.http.register_view(PrometheusView(config[DOMAIN][CONF_REQUIRES_AUTH]))

    conf: dict[str, Any] = config[DOMAIN]
    entity_filter: entityfilter.EntityFilter = conf[CONF_FILTER]
    namespace: str = conf[CONF_PROM_NAMESPACE]
    climate_units = hass.config.units.temperature_unit
    override_metric: str | None = conf.get(CONF_OVERRIDE_METRIC)
    default_metric: str | None = conf.get(CONF_DEFAULT_METRIC)
    component_config = EntityValues(
        conf[CONF_COMPONENT_CONFIG],
        conf[CONF_COMPONENT_CONFIG_DOMAIN],
        conf[CONF_COMPONENT_CONFIG_GLOB],
    )

    area_registry = ar.async_get(hass)
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    floor_registry = fr.async_get(hass)

    metrics = PrometheusMetrics(
        entity_filter,
        namespace,
        climate_units,
        component_config,
        override_metric,
        default_metric,
        area_registry,
        device_registry,
        entity_registry,
        floor_registry,
    )

    hass.bus.listen(EVENT_STATE_CHANGED, metrics.handle_state_changed_event)
    hass.bus.listen(
        EVENT_ENTITY_REGISTRY_UPDATED,
        metrics.handle_entity_registry_updated,
    )
    hass.bus.listen(
        EVENT_DEVICE_REGISTRY_UPDATED,
        metrics.handle_device_registry_updated,
    )
    hass.bus.listen(EVENT_AREA_REGISTRY_UPDATED, metrics.handle_area_registry_updated)
    hass.bus.listen(EVENT_FLOOR_REGISTRY_UPDATED, metrics.handle_floor_registry_updated)

    for floor in floor_registry.async_list_floors():
        metrics.handle_floor(floor)

    for area in area_registry.async_list_areas():
        metrics.handle_area(area)

    for state in hass.states.all():
        if entity_filter(state.entity_id):
            metrics.handle_state(state)

    return True


@dataclass(frozen=True, slots=True)
class MetricNameWithLabelValues:
    """Class to represent a metric with its label values.

    The prometheus client library doesn't easily allow us to get back the
    information we put into it. Specifically, it is very expensive to query
    which label values have been set for metrics.

    This class is used to hold a bit of data we need to efficiently remove
    labelsets from metrics.
    """

    metric_name: str
    label_values: tuple[str, ...]


class PrometheusMetrics:
    """Model all of the metrics which should be exposed to Prometheus."""

    def __init__(
        self,
        entity_filter: entityfilter.EntityFilter,
        namespace: str,
        climate_units: UnitOfTemperature,
        component_config: EntityValues,
        override_metric: str | None,
        default_metric: str | None,
        area_registry: ar.AreaRegistry,
        device_registry: dr.DeviceRegistry,
        entity_registry: er.EntityRegistry,
        floor_registry: fr.FloorRegistry,
    ) -> None:
        """Initialize Prometheus Metrics."""
        self._component_config = component_config
        self._override_metric = override_metric
        self._default_metric = default_metric
        self._filter = entity_filter
        self._sensor_metric_handlers: list[
            Callable[[State, str | None], str | None]
        ] = [
            self._sensor_override_component_metric,
            self._sensor_override_metric,
            self._sensor_timestamp_metric,
            self._sensor_attribute_metric,
            self._sensor_default_metric,
            self._sensor_fallback_metric,
        ]

        if namespace:
            self.metrics_prefix = f"{namespace}_"
        else:
            self.metrics_prefix = ""
        self._metrics: dict[str, MetricWrapperBase] = {}
        self._metrics_by_entity_id: dict[str, set[MetricNameWithLabelValues]] = (
            defaultdict(set)
        )
        self._climate_units = climate_units

        self._area_info_metrics: dict[str, MetricNameWithLabelValues] = {}
        self._floor_info_metrics: dict[str, MetricNameWithLabelValues] = {}

        self.area_registry = area_registry
        self.device_registry = device_registry
        self.entity_registry = entity_registry
        self.floor_registry = floor_registry

    def handle_state_changed_event(self, event: Event[EventStateChangedData]) -> None:
        """Handle new messages from the bus."""
        if (state := event.data.get("new_state")) is None:
            return

        if not self._filter(state.entity_id):
            _LOGGER.debug("Filtered out entity %s", state.entity_id)
            return

        if (
            old_state := event.data.get("old_state")
        ) is not None and old_state.attributes.get(
            ATTR_FRIENDLY_NAME
        ) != state.attributes.get(ATTR_FRIENDLY_NAME):
            self._remove_labelsets(old_state.entity_id)

        self.handle_state(state)

    def handle_state(self, state: State) -> None:
        """Add/update a state in Prometheus."""
        entity_id = state.entity_id
        _LOGGER.debug("Handling state update for %s", entity_id)

        if not self._metrics_by_entity_id[state.entity_id]:
            area_id = self._find_area_id(state.entity_id)
            if area_id is not None:
                self._add_entity_info(state.entity_id, area_id)

        labels = self._labels(state)

        self._metric(
            "state_change",
            prometheus_client.Counter,
            "The number of state changes",
            labels,
        ).inc()

        self._metric(
            "entity_available",
            prometheus_client.Gauge,
            "Entity is available (not in the unavailable or unknown state)",
            labels,
        ).set(float(state.state not in IGNORED_STATES))

        self._metric(
            "last_updated_time_seconds",
            prometheus_client.Gauge,
            "The last_updated timestamp",
            labels,
        ).set(state.last_updated.timestamp())

        if state.state in IGNORED_STATES:
            self._remove_labelsets(
                entity_id,
                {
                    "state_change",
                    "entity_available",
                    "last_updated_time_seconds",
                    "entity_info",
                },
            )
        else:
            domain, _ = hacore.split_entity_id(entity_id)
            handler = f"_handle_{domain}"
            if hasattr(self, handler) and state.state:
                getattr(self, handler)(state)

    def handle_entity_registry_updated(
        self, event: Event[EventEntityRegistryUpdatedData]
    ) -> None:
        """Listen for deleted, disabled or renamed entities and remove them from the Prometheus Registry."""
        if event.data["action"] in (None, "create"):
            return

        entity_id = event.data.get("entity_id")
        _LOGGER.debug("Handling entity update for %s", entity_id)

        metrics_entity_id: str | None = None

        if event.data["action"] == "remove":
            metrics_entity_id = entity_id
        elif event.data["action"] == "update":
            changes = event.data["changes"]

            if "entity_id" in changes:
                metrics_entity_id = changes["entity_id"]
            elif "disabled_by" in changes:
                metrics_entity_id = entity_id
            elif "area_id" in changes or "device_id" in changes:
                if entity_id is not None:
                    self._remove_entity_info(entity_id)
                    area_id = self._find_area_id(entity_id)
                    if area_id is not None:
                        self._add_entity_info(entity_id, area_id)

        if metrics_entity_id:
            self._remove_labelsets(metrics_entity_id)

    def handle_device_registry_updated(
        self, event: Event[EventDeviceRegistryUpdatedData]
    ) -> None:
        """Listen for changes of devices' area_id."""
        if event.data["action"] != "update" or "area_id" not in event.data["changes"]:
            return

        device_id = event.data.get("device_id")

        if device_id is None:
            return

        _LOGGER.debug("Handling device update for %s", device_id)

        device = self.device_registry.async_get(device_id)
        if device is None:
            return

        area_id = device.area_id

        for entity_id in (
            entity.entity_id
            for entity in er.async_entries_for_device(self.entity_registry, device_id)
            if entity.area_id is None and entity.entity_id in self._metrics_by_entity_id
        ):
            self._remove_entity_info(entity_id)
            if area_id is not None:
                self._add_entity_info(entity_id, area_id)

    def handle_area_registry_updated(
        self, event: Event[EventAreaRegistryUpdatedData]
    ) -> None:
        """Listen for changes to areas."""

        area_id = event.data.get("area_id")

        if area_id is None:
            return

        action = event.data["action"]

        _LOGGER.debug("Handling area update for %s (%s)", area_id, action)

        if action in {"update", "remove"}:
            metric = self._area_info_metrics.pop(area_id, None)
            if metric is not None:
                metric_name, label_values = astuple(metric)
                self._metrics[metric_name].remove(*label_values)
        if action in {"update", "create"}:
            area = self.area_registry.async_get_area(area_id)
            if area is not None:
                self.handle_area(area)

    def handle_area(self, area: AreaEntry) -> None:
        """Add/update an area in Prometheus."""
        metric_name = "area_info"
        labels = {
            "area": area.id,
            "area_name": area.name,
            "floor": area.floor_id if area.floor_id is not None else "",
        }
        self._area_info_metrics[labels["area"]] = MetricNameWithLabelValues(
            metric_name, tuple(labels.values())
        )
        self._metric(
            metric_name,
            prometheus_client.Gauge,
            "Area information",
            labels,
        ).set(1.0)

    def handle_floor_registry_updated(
        self, event: Event[EventFloorRegistryUpdatedData]
    ) -> None:
        """Listen for changes to floors."""

        floor_id = event.data.get("floor_id")

        if floor_id is None:
            return

        action = event.data["action"]

        _LOGGER.debug("Handling floor update for %s (%s)", floor_id, action)

        if action in {"update", "remove"}:
            metric = self._floor_info_metrics.pop(str(floor_id), None)
            if metric is not None:
                metric_name, label_values = astuple(metric)
                self._metrics[metric_name].remove(*label_values)
        if action in {"update", "create"}:
            floor = self.floor_registry.async_get_floor(str(floor_id))
            if floor is not None:
                self.handle_floor(floor)

    def handle_floor(self, floor: FloorEntry) -> None:
        """Add/update a floor in Prometheus."""
        metric_name = "floor_info"
        labels = {
            "floor": floor.floor_id,
            "floor_name": floor.name,
            "floor_level": str(floor.level) if floor.level is not None else "",
        }
        self._floor_info_metrics[labels["floor"]] = MetricNameWithLabelValues(
            metric_name, tuple(labels.values())
        )
        self._metric(
            metric_name,
            prometheus_client.Gauge,
            "Floor information",
            labels,
        ).set(1.0)

    def _remove_labelsets(
        self,
        entity_id: str,
        ignored_metric_names: set[str] | None = None,
    ) -> None:
        """Remove labelsets matching the given entity id from all non-ignored metrics."""
        if ignored_metric_names is None:
            ignored_metric_names = set()
        metric_set = self._metrics_by_entity_id[entity_id]
        removed_metrics = set()
        for metric in metric_set:
            metric_name, label_values = astuple(metric)
            if metric_name in ignored_metric_names:
                continue

            _LOGGER.debug(
                "Removing labelset %s from %s for entity_id: %s",
                label_values,
                metric_name,
                entity_id,
            )
            removed_metrics.add(metric)
            self._metrics[metric_name].remove(*label_values)
        metric_set -= removed_metrics
        if not metric_set:
            del self._metrics_by_entity_id[entity_id]

    def _handle_attributes(self, state: State) -> None:
        for key, value in state.attributes.items():
            try:
                value = float(value)
            except (ValueError, TypeError):
                continue

            self._metric(
                f"{state.domain}_attr_{key.lower()}",
                prometheus_client.Gauge,
                f"{key} attribute of {state.domain} entity",
                self._labels(state),
            ).set(value)

    def _metric[_MetricBaseT: MetricWrapperBase](
        self,
        metric_name: str,
        factory: type[_MetricBaseT],
        documentation: str,
        labels: dict[str, str],
    ) -> _MetricBaseT:
        try:
            metric = cast(_MetricBaseT, self._metrics[metric_name])
        except KeyError:
            full_metric_name = self._sanitize_metric_name(
                f"{self.metrics_prefix}{metric_name}"
            )
            self._metrics[metric_name] = factory(
                full_metric_name,
                documentation,
                labels.keys(),
                registry=prometheus_client.REGISTRY,
            )
            metric = cast(_MetricBaseT, self._metrics[metric_name])
        if "entity" in labels:
            self._metrics_by_entity_id[labels["entity"]].add(
                MetricNameWithLabelValues(metric_name, tuple(labels.values()))
            )
        return metric.labels(**labels)

    @staticmethod
    def _sanitize_metric_name(metric: str) -> str:
        metric.replace("\u03bc", "\u00b5")
        return "".join(
            [c if c in ALLOWED_METRIC_CHARS else f"u{hex(ord(c))}" for c in metric]
        )

    @staticmethod
    def state_as_number(state: State) -> float | None:
        """Return state as a float, or None if state cannot be converted."""
        try:
            if state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP:
                value = as_timestamp(state.state)
            else:
                value = state_helper.state_as_number(state)
        except ValueError:
            _LOGGER.debug("Could not convert %s to float", state)
            value = None
        return value

    @staticmethod
    def _labels(
        state: State,
        extra_labels: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if extra_labels is None:
            extra_labels = {}
        labels = {
            "entity": state.entity_id,
            "domain": state.domain,
            "friendly_name": state.attributes.get(ATTR_FRIENDLY_NAME),
        }
        if not labels.keys().isdisjoint(extra_labels.keys()):
            conflicting_keys = labels.keys() & extra_labels.keys()
            raise ValueError(
                f"extra_labels contains conflicting keys: {conflicting_keys}"
            )
        return labels | extra_labels

    def _remove_entity_info(self, entity_id: str) -> None:
        """Remove an entity-area-relation in Prometheus."""
        self._remove_labelsets(
            entity_id,
            {
                metric_set.metric_name
                for metric_set in self._metrics_by_entity_id[entity_id]
                if metric_set.metric_name != "entity_info"
            },
        )

    def _add_entity_info(self, entity_id: str, area_id: str) -> None:
        """Add/update an entity-area-relation in Prometheus."""
        self._metric(
            "entity_info",
            prometheus_client.Gauge,
            "The area of an entity",
            {
                "entity": entity_id,
                "area": area_id,
            },
        ).set(1.0)

    def _find_area_id(self, entity_id: str) -> str | None:
        """Find area of entity or parent device."""
        entity = self.entity_registry.async_get(entity_id)

        if entity is None:
            return None

        area_id = entity.area_id

        if area_id is None and entity.device_id is not None:
            device = self.device_registry.async_get(entity.device_id)
            if device is not None:
                area_id = device.area_id

        return area_id

    def _battery_metric(self, state: State) -> None:
        if (battery_level := state.attributes.get(ATTR_BATTERY_LEVEL)) is None:
            return

        try:
            value = float(battery_level)
        except ValueError:
            return

        self._metric(
            "battery_level_percent",
            prometheus_client.Gauge,
            "Battery level as a percentage of its capacity",
            self._labels(state),
        ).set(value)

    def _temperature_metric(
        self, state: State, attr: str, metric_name: str, metric_description: str
    ) -> None:
        if (temp := state.attributes.get(attr)) is None:
            return

        if self._climate_units == UnitOfTemperature.FAHRENHEIT:
            temp = TemperatureConverter.convert(
                temp, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS
            )
        self._metric(
            metric_name,
            prometheus_client.Gauge,
            metric_description,
            self._labels(state),
        ).set(temp)

    def _bool_metric(
        self,
        state: State,
        attr: str,
        metric_name: str,
        metric_description: str,
        true_values: set[Any] | None = None,
    ) -> None:
        value = state.attributes.get(attr)
        if value is None:
            return

        result = bool(value) if true_values is None else value in true_values
        self._metric(
            metric_name,
            prometheus_client.Gauge,
            metric_description,
            self._labels(state),
        ).set(float(result))

    def _float_metric(
        self,
        state: State,
        attr: str,
        metric_name: str,
        metric_description: str,
    ) -> None:
        value = state.attributes.get(attr)
        if value is None:
            return

        self._metric(
            metric_name,
            prometheus_client.Gauge,
            metric_description,
            self._labels(state),
        ).set(float(value))

    def _enum_metric(
        self,
        state: State,
        current_value: Any | None,
        values: Sequence[str] | None,
        metric_name: str,
        metric_description: str,
        enum_label_name: str,
    ) -> None:
        if current_value is None or values is None:
            return

        for value in values:
            self._metric(
                metric_name,
                prometheus_client.Gauge,
                metric_description,
                self._labels(state, {enum_label_name: value}),
            ).set(float(value == current_value))

    def _numeric_metric(self, state: State, domain: str, title: str) -> None:
        if (value := self.state_as_number(state)) is None:
            return

        if unit := self._unit_string(state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)):
            metric = self._metric(
                f"{domain}_state_{unit}",
                prometheus_client.Gauge,
                f"State of the {title} measured in {unit}",
                self._labels(state),
            )
        else:
            metric = self._metric(
                f"{domain}_state",
                prometheus_client.Gauge,
                f"State of the {title}",
                self._labels(state),
            )

        if (
            state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            == UnitOfTemperature.FAHRENHEIT
        ):
            value = TemperatureConverter.convert(
                value, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS
            )

        metric.set(value)

    def _handle_binary_sensor(self, state: State) -> None:
        self._numeric_metric(state, "binary_sensor", "binary boolean")

    def _handle_input_boolean(self, state: State) -> None:
        self._numeric_metric(state, "input_boolean", "input boolean")

    def _handle_input_number(self, state: State) -> None:
        self._numeric_metric(state, "input_number", "input number")

    def _handle_number(self, state: State) -> None:
        self._numeric_metric(state, "number", "number")

    def _handle_device_tracker(self, state: State) -> None:
        self._numeric_metric(state, "device_tracker", "device tracker")

    def _handle_person(self, state: State) -> None:
        self._numeric_metric(state, "person", "person")

    def _handle_lock(self, state: State) -> None:
        self._numeric_metric(state, "lock", "lock")

    def _handle_cover(self, state: State) -> None:
        self._enum_metric(
            state,
            state.state,
            [STATE_CLOSED, STATE_CLOSING, STATE_OPEN, STATE_OPENING],
            "cover_state",
            "State of the cover (0/1)",
            "state",
        )
        self._float_metric(
            state,
            ATTR_CURRENT_POSITION,
            "cover_position",
            "Position of the cover (0-100)",
        )
        self._float_metric(
            state,
            ATTR_CURRENT_TILT_POSITION,
            "cover_tilt_position",
            "Tilt Position of the cover (0-100)",
        )

    def _handle_light(self, state: State) -> None:
        if (value := self.state_as_number(state)) is None:
            return

        brightness = state.attributes.get(ATTR_BRIGHTNESS)
        if state.state == STATE_ON and brightness is not None:
            value = float(brightness) / 255.0
        value = value * 100

        self._metric(
            "light_brightness_percent",
            prometheus_client.Gauge,
            "Light brightness percentage (0..100)",
            self._labels(state),
        ).set(value)

    def _handle_climate(self, state: State) -> None:
        self._temperature_metric(
            state,
            ATTR_TEMPERATURE,
            "climate_target_temperature_celsius",
            "Target temperature in degrees Celsius",
        )
        self._temperature_metric(
            state,
            ATTR_TARGET_TEMP_HIGH,
            "climate_target_temperature_high_celsius",
            "Target high temperature in degrees Celsius",
        )
        self._temperature_metric(
            state,
            ATTR_TARGET_TEMP_LOW,
            "climate_target_temperature_low_celsius",
            "Target low temperature in degrees Celsius",
        )
        self._temperature_metric(
            state,
            ATTR_CURRENT_TEMPERATURE,
            "climate_current_temperature_celsius",
            "Current temperature in degrees Celsius",
        )

        self._enum_metric(
            state,
            (
                (attr := state.attributes.get(ATTR_HVAC_ACTION))
                and getattr(attr, "value", attr)
            ),
            [action.value for action in HVACAction],
            "climate_action",
            "HVAC action",
            "action",
        )
        self._enum_metric(
            state,
            state.state,
            state.attributes.get(ATTR_HVAC_MODES),
            "climate_mode",
            "HVAC mode",
            "mode",
        )
        self._enum_metric(
            state,
            state.attributes.get(ATTR_PRESET_MODE),
            state.attributes.get(ATTR_PRESET_MODES),
            "climate_preset_mode",
            "Preset mode enum",
            "mode",
        )
        self._enum_metric(
            state,
            state.attributes.get(ATTR_FAN_MODE),
            state.attributes.get(ATTR_FAN_MODES),
            "climate_fan_mode",
            "Fan mode enum",
            "mode",
        )

    def _handle_humidifier(self, state: State) -> None:
        self._numeric_metric(state, "humidifier", "humidifier")

        self._float_metric(
            state,
            ATTR_HUMIDITY,
            "humidifier_target_humidity_percent",
            "Target Relative Humidity",
        )

        self._enum_metric(
            state,
            state.attributes.get(ATTR_MODE),
            state.attributes.get(ATTR_AVAILABLE_MODES),
            "humidifier_mode",
            "Humidifier Mode",
            "mode",
        )

    def _handle_water_heater(self, state: State) -> None:
        # Temperatures
        self._temperature_metric(
            state,
            ATTR_TEMPERATURE,
            "water_heater_temperature_celsius",
            "Target temperature in degrees Celsius",
        )
        self._temperature_metric(
            state,
            WATER_HEATER_ATTR_CURRENT_TEMPERATURE,
            "water_heater_current_temperature_celsius",
            "Target temperature in degrees Celsius",
        )
        self._temperature_metric(
            state,
            WATER_HEATER_ATTR_TARGET_TEMP_HIGH,
            "water_heater_target_temperature_high_celsius",
            "Target high temperature in degrees Celsius",
        )
        self._temperature_metric(
            state,
            WATER_HEATER_ATTR_TARGET_TEMP_LOW,
            "water_heater_target_temperature_low_celsius",
            "Target low temperature in degrees Celsius",
        )
        self._temperature_metric(
            state,
            WATER_HEATER_ATTR_MIN_TEMP,
            "water_heater_min_temperature_celsius",
            "Minimum allowed temperature in degrees Celsius",
        )
        self._temperature_metric(
            state,
            WATER_HEATER_ATTR_MAX_TEMP,
            "water_heater_max_temperature_celsius",
            "Maximum allowed temperature in degrees Celsius",
        )
        self._enum_metric(
            state,
            state.attributes.get(WATER_HEATER_ATTR_OPERATION_MODE) or state.state,
            state.attributes.get(WATER_HEATER_ATTR_OPERATION_LIST),
            "water_heater_operation_mode",
            "Water heater operation mode",
            "mode",
        )

        # Away mode bool
        self._bool_metric(
            state,
            WATER_HEATER_ATTR_AWAY_MODE,
            "water_heater_away_mode",
            "Whether away mode is on (0/1)",
            {STATE_ON},
        )

    def _handle_switch(self, state: State) -> None:
        self._numeric_metric(state, "switch", "switch")
        self._handle_attributes(state)

    def _handle_fan(self, state: State) -> None:
        self._numeric_metric(state, "fan", "fan")
        self._float_metric(
            state, ATTR_PERCENTAGE, "fan_speed_percent", "Fan speed percent (0-100)"
        )
        self._bool_metric(
            state,
            ATTR_OSCILLATING,
            "fan_is_oscillating",
            "Whether the fan is oscillating (0/1)",
        )

        self._enum_metric(
            state,
            state.attributes.get(ATTR_PRESET_MODE),
            state.attributes.get(ATTR_PRESET_MODES),
            "fan_preset_mode",
            "Fan preset mode enum",
            "mode",
        )

        fan_direction = state.attributes.get(ATTR_DIRECTION)
        if fan_direction in {DIRECTION_FORWARD, DIRECTION_REVERSE}:
            self._bool_metric(
                state,
                ATTR_DIRECTION,
                "fan_direction_reversed",
                "Fan direction reversed (bool)",
                {DIRECTION_REVERSE},
            )

    def _handle_zwave(self, state: State) -> None:
        self._battery_metric(state)

    def _handle_automation(self, state: State) -> None:
        self._metric(
            "automation_triggered_count",
            prometheus_client.Counter,
            "Count of times an automation has been triggered",
            self._labels(state),
        ).inc()

    def _handle_counter(self, state: State) -> None:
        if (value := self.state_as_number(state)) is None:
            return

        self._metric(
            "counter_value",
            prometheus_client.Gauge,
            "Value of counter entities",
            self._labels(state),
        ).set(value)

    def _handle_update(self, state: State) -> None:
        self._numeric_metric(state, "update", "update")

    def _handle_alarm_control_panel(self, state: State) -> None:
        self._enum_metric(
            state,
            state.state,
            [alarm_state.value for alarm_state in AlarmControlPanelState],
            "alarm_control_panel_state",
            "State of the alarm control panel (0/1)",
            "state",
        )

    def _handle_sensor(self, state: State) -> None:
        unit = self._unit_string(state.attributes.get(ATTR_UNIT_OF_MEASUREMENT))

        for metric_handler in self._sensor_metric_handlers:
            metric = metric_handler(state, unit)
            if metric is not None:
                break

        if metric is not None and (value := self.state_as_number(state)) is not None:
            documentation = "State of the sensor"
            if unit:
                documentation = f"Sensor data measured in {unit}"

            if (
                state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
                == UnitOfTemperature.FAHRENHEIT
            ):
                value = TemperatureConverter.convert(
                    value, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS
                )
            self._metric(
                metric,
                prometheus_client.Gauge,
                documentation,
                self._labels(state),
            ).set(value)

        self._battery_metric(state)

    def _sensor_default_metric(self, state: State, unit: str | None) -> str | None:
        """Get default metric."""
        return self._default_metric

    @staticmethod
    def _sensor_attribute_metric(state: State, unit: str | None) -> str | None:
        """Get metric based on device class attribute."""
        metric = state.attributes.get(ATTR_DEVICE_CLASS)
        if metric is not None:
            return f"sensor_{metric}_{unit}"
        return None

    @staticmethod
    def _sensor_timestamp_metric(state: State, unit: str | None) -> str | None:
        """Get metric for timestamp sensors, which have no unit of measurement attribute."""
        metric = state.attributes.get(ATTR_DEVICE_CLASS)
        if metric == SensorDeviceClass.TIMESTAMP:
            return f"sensor_{metric}_seconds"
        return None

    def _sensor_override_metric(self, state: State, unit: str | None) -> str | None:
        """Get metric from override in configuration."""
        if self._override_metric:
            return self._override_metric
        return None

    def _sensor_override_component_metric(
        self, state: State, unit: str | None
    ) -> str | None:
        """Get metric from override in component configuration."""
        return self._component_config.get(state.entity_id).get(CONF_OVERRIDE_METRIC)

    @staticmethod
    def _sensor_fallback_metric(state: State, unit: str | None) -> str | None:
        """Get metric from fallback logic for compatibility."""
        if unit not in (None, ""):
            return f"sensor_unit_{unit}"
        return "sensor_state"

    @staticmethod
    def _unit_string(unit: str | None) -> str | None:
        """Get a formatted string of the unit."""
        if unit is None:
            return None

        units = {
            UnitOfTemperature.CELSIUS: "celsius",
            UnitOfTemperature.FAHRENHEIT: "celsius",  # F should go into C metric
            PERCENTAGE: "percent",
        }
        default = unit.replace("/", "_per_")
        # Unit conversion for CONCENTRATION_MICROGRAMS_PER_CUBIC_METER "μg/m³"
        # "μ" == "\u03bc" but the API uses "\u00b5"
        default = default.replace("\u03bc", "\u00b5")
        default = default.lower()
        return units.get(unit, default)


class PrometheusView(HomeAssistantView):
    """Handle Prometheus requests."""

    url = API_ENDPOINT
    name = "api:prometheus"

    def __init__(self, requires_auth: bool) -> None:
        """Initialize Prometheus view."""
        self.requires_auth = requires_auth

    async def get(self, request: web.Request) -> web.Response:
        """Handle request for Prometheus metrics."""
        _LOGGER.debug("Received Prometheus metrics request")

        hass = request.app[KEY_HASS]
        body = await hass.async_add_executor_job(
            prometheus_client.generate_latest, prometheus_client.REGISTRY
        )
        return web.Response(
            body=body,
            content_type=CONTENT_TYPE_TEXT_PLAIN,
        )
