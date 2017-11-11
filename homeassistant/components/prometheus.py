"""
Support for Prometheus metrics export.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/prometheus/
"""
import asyncio
import logging

import voluptuous as vol
from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.components import recorder
from homeassistant.const import (
    CONF_DOMAINS, CONF_ENTITIES, CONF_EXCLUDE, CONF_INCLUDE,
    EVENT_STATE_CHANGED, TEMP_FAHRENHEIT, CONTENT_TYPE_TEXT_PLAIN,
    ATTR_TEMPERATURE, ATTR_UNIT_OF_MEASUREMENT)
from homeassistant import core as hacore
from homeassistant.helpers import state as state_helper
from homeassistant.util.temperature import fahrenheit_to_celsius

REQUIREMENTS = ['prometheus_client==0.1.0']

_LOGGER = logging.getLogger(__name__)

API_ENDPOINT = '/api/prometheus'

DOMAIN = 'prometheus'
DEPENDENCIES = ['http']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: recorder.FILTER_SCHEMA,
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Activate Prometheus component."""
    import prometheus_client

    hass.http.register_view(PrometheusView(prometheus_client))

    conf = config.get(DOMAIN, {})
    exclude = conf.get(CONF_EXCLUDE, {})
    include = conf.get(CONF_INCLUDE, {})
    metrics = Metrics(prometheus_client, exclude, include)

    hass.bus.listen(EVENT_STATE_CHANGED, metrics.handle_event)
    return True


class Metrics(object):
    """Model all of the metrics which should be exposed to Prometheus."""

    def __init__(self, prometheus_client, exclude, include):
        """Initialize Prometheus Metrics."""
        self.prometheus_client = prometheus_client
        self.exclude = exclude.get(CONF_ENTITIES, []) + \
            exclude.get(CONF_DOMAINS, [])
        self.include_domains = include.get(CONF_DOMAINS, [])
        self.include_entities = include.get(CONF_ENTITIES, [])
        self._metrics = {}

    def handle_event(self, event):
        """Listen for new messages on the bus, and add them to Prometheus."""
        state = event.data.get('new_state')
        if state is None:
            return

        entity_id = state.entity_id
        _LOGGER.debug("Handling state update for %s", entity_id)
        domain, _ = hacore.split_entity_id(entity_id)

        if entity_id in self.exclude:
            return
        if domain in self.exclude and entity_id not in self.include_entities:
            return
        if self.include_domains and domain not in self.include_domains:
            return
        if not self.exclude and (self.include_entities and
                                 entity_id not in self.include_entities):
            return

        handler = '_handle_{}'.format(domain)

        if hasattr(self, handler):
            getattr(self, handler)(state)

        metric = self._metric(
            'state_change',
            self.prometheus_client.Counter,
            'The number of state changes',
        )
        metric.labels(**self._labels(state)).inc()

    def _metric(self, metric, factory, documentation, labels=None):
        if labels is None:
            labels = ['entity', 'friendly_name', 'domain']

        try:
            return self._metrics[metric]
        except KeyError:
            self._metrics[metric] = factory(metric, documentation, labels)
            return self._metrics[metric]

    @staticmethod
    def _labels(state):
        return {
            'entity': state.entity_id,
            'domain': state.domain,
            'friendly_name': state.attributes.get('friendly_name'),
        }

    def _battery(self, state):
        if 'battery_level' in state.attributes:
            metric = self._metric(
                'battery_level_percent',
                self.prometheus_client.Gauge,
                'Battery level as a percentage of its capacity',
            )
            try:
                value = float(state.attributes['battery_level'])
                metric.labels(**self._labels(state)).set(value)
            except ValueError:
                pass

    def _handle_binary_sensor(self, state):
        metric = self._metric(
            'binary_sensor_state',
            self.prometheus_client.Gauge,
            'State of the binary sensor (0/1)',
        )
        value = state_helper.state_as_number(state)
        metric.labels(**self._labels(state)).set(value)

    def _handle_device_tracker(self, state):
        metric = self._metric(
            'device_tracker_state',
            self.prometheus_client.Gauge,
            'State of the device tracker (0/1)',
        )
        value = state_helper.state_as_number(state)
        metric.labels(**self._labels(state)).set(value)

    def _handle_light(self, state):
        metric = self._metric(
            'light_state',
            self.prometheus_client.Gauge,
            'Load level of a light (0..1)',
        )

        try:
            if 'brightness' in state.attributes:
                value = state.attributes['brightness'] / 255.0
            else:
                value = state_helper.state_as_number(state)
            value = value * 100
            metric.labels(**self._labels(state)).set(value)
        except ValueError:
            pass

    def _handle_lock(self, state):
        metric = self._metric(
            'lock_state',
            self.prometheus_client.Gauge,
            'State of the lock (0/1)',
        )
        value = state_helper.state_as_number(state)
        metric.labels(**self._labels(state)).set(value)

    def _handle_climate(self, state):
        temp = state.attributes.get(ATTR_TEMPERATURE)
        if temp:
            unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            if unit == TEMP_FAHRENHEIT:
                temp = fahrenheit_to_celsius(temp)
            metric = self._metric(
                'temperature_c', self.prometheus_client.Gauge,
                'Temperature in degrees Celsius')
            metric.labels(**self._labels(state)).set(temp)

        metric = self._metric(
            'climate_state', self.prometheus_client.Gauge,
            'State of the thermostat (0/1)')
        try:
            value = state_helper.state_as_number(state)
            metric.labels(**self._labels(state)).set(value)
        except ValueError:
            pass

    def _handle_sensor(self, state):

        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        metric = state.entity_id.split(".")[1]

        if '_' not in str(metric):
            metric = state.entity_id.replace('.', '_')

        try:
            int(metric.split("_")[-1])
            metric = "_".join(metric.split("_")[:-1])
        except ValueError:
            pass

        _metric = self._metric(metric, self.prometheus_client.Gauge,
                               state.entity_id)

        try:
            value = state_helper.state_as_number(state)
            if unit == TEMP_FAHRENHEIT:
                value = fahrenheit_to_celsius(value)
            _metric.labels(**self._labels(state)).set(value)
        except ValueError:
            pass

        self._battery(state)

    def _handle_switch(self, state):
        metric = self._metric(
            'switch_state',
            self.prometheus_client.Gauge,
            'State of the switch (0/1)',
        )

        try:
            value = state_helper.state_as_number(state)
            metric.labels(**self._labels(state)).set(value)
        except ValueError:
            pass

    def _handle_zwave(self, state):
        self._battery(state)

    def _handle_automation(self, state):
        metric = self._metric(
            'automation_triggered_count',
            self.prometheus_client.Counter,
            'Count of times an automation has been triggered',
        )

        metric.labels(**self._labels(state)).inc()


class PrometheusView(HomeAssistantView):
    """Handle Prometheus requests."""

    url = API_ENDPOINT
    name = 'api:prometheus'

    def __init__(self, prometheus_client):
        """Initialize Prometheus view."""
        self.prometheus_client = prometheus_client

    @asyncio.coroutine
    def get(self, request):
        """Handle request for Prometheus metrics."""
        _LOGGER.debug("Received Prometheus metrics request")

        return web.Response(
            body=self.prometheus_client.generate_latest(),
            content_type=CONTENT_TYPE_TEXT_PLAIN)
