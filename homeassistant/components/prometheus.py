"""
Support for Prometheus metrics export

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/prometheus/
"""
import asyncio
import logging

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.const import (ATTR_HIDDEN, EVENT_STATE_CHANGED,
                                 TEMP_CELSIUS, TEMP_FAHRENHEIT)
from homeassistant import core as ha
from homeassistant.helpers import state as state_helper

_LOGGER = logging.getLogger(__name__)

ATTR_PROMETHEUS_HIDDEN = 'prometheus_hidden'

REQUIREMENTS = ['prometheus_client==0.0.18']

DOMAIN = 'prometheus'
DEPENDENCIES = ['http']


def setup(hass, config):
    import prometheus_client

    hass.http.register_view(PrometheusView(hass, prometheus_client))

    metrics = Metrics(prometheus_client)

    hass.bus.listen(EVENT_STATE_CHANGED, metrics.handle_event)

    return True


class Metrics:
    def __init__(self, prometheus_client):
        self.prometheus_client = prometheus_client
        self._metrics = {}

    def handle_event(self, event):
        """Listen for new messages on the bus, and add them to Prometheus"""
        state = event.data.get('new_state')
        if state is None:
            return

        _LOGGER.info("Handling state update for %s", state.entity_id)

        if (state.attributes.get(ATTR_HIDDEN) or
                state.attributes.get(ATTR_PROMETHEUS_HIDDEN)):
            return

        domain, _ = ha.split_entity_id(state.entity_id)
        handler = '_handle_' + domain

        if hasattr(self, handler):
            getattr(self, handler)(state)

    def _metric(self, metric, factory, documentation, labels=None):
        if labels is None:
            labels = ['entity', 'friendly_name']

        try:
            return self._metrics[metric]
        except KeyError:
            self._metrics[metric] = factory(metric, documentation, labels)
            return self._metrics[metric]

    def _labels(self, state):
        return {
            'entity': state.entity_id,
            'friendly_name': state.attributes.get('friendly_name'),
        }

    def _battery(self, state):
        if 'battery_level' in state.attributes:
            m = self._metric(
                'battery_level_percent',
                self.prometheus_client.Gauge,
                'Battery level as a percentage of its capacity',
            )
            try:
                value = float(state.attributes['battery_level'])
                m.labels(**self._labels(state)).set(value)
            except ValueError:
                pass

    def _handle_binary_sensor(self, state):
        m = self._metric(
            'binary_sensor_state',
            self.prometheus_client.Gauge,
            'State of the binary sensor (0/1)',
        )

        value = state_helper.state_as_number(state)
        m.labels(**self._labels(state)).set(value)

    def _handle_device_tracker(self, state):
        m = self._metric(
            'device_tracker_state',
            self.prometheus_client.Gauge,
            'State of the device tracker (0/1)',
        )

        value = state_helper.state_as_number(state)
        m.labels(**self._labels(state)).set(value)

    def _handle_light(self, state):
        m = self._metric(
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
            m.labels(**self._labels(state)).set(value)
        except ValueError:
            pass

    def _handle_sensor(self, state):

        _sensor_types = {
            TEMP_CELSIUS: (
                'temperature_c', self.prometheus_client.Gauge,
                'Temperature in degrees Celsius',
            ),
            TEMP_FAHRENHEIT: (
                'temperature_c', self.prometheus_client.Gauge,
                'Temperature in degrees Celsius',
            ),
            '%': (
                'relative_humidity', self.prometheus_client.Gauge,
                'Relative humidity (0..100)',
            ),
            'lux': (
                'light_lux', self.prometheus_client.Gauge,
                'Light level in lux',
            ),
            'kWh': (
                'electricity_used_kwh', self.prometheus_client.Gauge,
                'Electricity used by this device in KWh',
            ),
            'V': (
                'voltage', self.prometheus_client.Gauge,
                'Currently reported voltage in Volts',
            ),
            'W': (
                'electricity_usage_w', self.prometheus_client.Gauge,
                'Currently reported electricity draw in Watts',
            ),
        }

        unit = state.attributes.get('unit_of_measurement')
        m = _sensor_types.get(unit)

        if m is not None:
            m = self._metric(*m)
            try:
                value = state_helper.state_as_number(state)
                m.labels(**self._labels(state)).set(value)
            except ValueError:
                pass

        self._battery(state)

    def _handle_switch(self, state):
        m = self._metric(
            'switch_state',
            self.prometheus_client.Gauge,
            'State of the switch (0/1)',
        )

        value = state_helper.state_as_number(state)
        m.labels(**self._labels(state)).set(value)


class PrometheusView(HomeAssistantView):
    url = '/api/prometheus'
    name = 'api:prometheus'

    def __init__(self, hass, prometheus_client):
        super().__init__(hass)
        self.prometheus_client = prometheus_client

    @asyncio.coroutine
    def get(self, request):
        """Handle request for Prometheus metrics"""
        _LOGGER.debug('Received Prometheus metrics request')

        return web.Response(
            body=self.prometheus_client.generate_latest(),
            content_type="text/plain")
