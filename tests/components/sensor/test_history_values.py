"""The test for the History Values sensor platform."""
import asyncio
from datetime import timedelta
from unittest.mock import patch

from homeassistant.const import STATE_UNKNOWN
from homeassistant.setup import async_setup_component
from homeassistant.components import recorder
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.sensor.history_values import (
    DOMAIN as HVS_DOMAIN, HistoryValuesSensor, TYPE_AVG, TYPE_LOW, TYPE_PEAK,
    TYPE_RANGE)
import homeassistant.core as ha
from homeassistant.helpers.template import Template
import homeassistant.util.dt as dt_util

from tests.common import assert_setup_component


async def async_init_recorder(hass, add_config=None):
    """Set up an in-memory recorder."""
    config = dict(add_config) if add_config else {}
    config[recorder.CONF_DB_URL] = 'sqlite://'  # In memory DB

    with patch('homeassistant.components.recorder.migration.migrate_schema'):
        assert await async_setup_component(hass, recorder.DOMAIN,
                                           {recorder.DOMAIN: config})
        assert recorder.DOMAIN in hass.config.components


async def test_setup_sensor(hass):
    """Test platform setup."""
    await async_init_recorder(hass)
    with assert_setup_component(1, SENSOR_DOMAIN):
        await async_setup_component(
            hass, SENSOR_DOMAIN, {
                SENSOR_DOMAIN: {
                    'platform': HVS_DOMAIN,
                    'name': 'Test Sensor',
                    'type': TYPE_PEAK,
                    'target_entity_id': 'sensor.test_target',
                    'start': '{{ now().replace(hour=0)'
                             '.replace(minute=0).replace(second=0) }}',
                    'duration': '02:00',
                }
            })
    state = hass.states.get('sensor.test_sensor')
    assert state.state == STATE_UNKNOWN


async def test_setup_invalid_config(hass):
    """Test platform setup with invalid config."""
    invalid_config = {
        'platform': HVS_DOMAIN,
        'name': 'Test Sensor',
        'target_entity_id': 'sensor.test_target',
        'start': '{{ now().replace(hour=0)'
                 '.replace(minute=0).replace(second=0) }}',
        'duration': '02:00',
    }
    with assert_setup_component(0):
        await async_setup_component(hass, SENSOR_DOMAIN, invalid_config)


async def test_period_parsing(hass):
    """Test the conversion from templates to period."""
    today = Template('{{ now().replace(hour=0).replace(minute=0)'
                     '.replace(second=0) }}', hass)
    duration = timedelta(hours=2, minutes=1)

    sensor1 = HistoryValuesSensor(
        'test', 'sensor.test_sensor', TYPE_PEAK, 'sensor.test_target', None,
        today, None, duration, None)
    sensor2 = HistoryValuesSensor(
        'test', 'sensor.test_sensor2', TYPE_LOW, 'sensor.test_target', None,
        None, today, duration, None)

    # pylint: disable=protected-access
    await sensor1.update_period()
    sensor1_start, sensor1_end = sensor1._period
    await sensor2.update_period()
    sensor2_start, sensor2_end = sensor2._period

    # Start = 00:00:00
    assert sensor1_start.hour == 0
    assert sensor1_start.minute == 0
    assert sensor1_start.second == 0

    # End = 02:01:00
    assert sensor1_end.hour == 2
    assert sensor1_end.minute == 1
    assert sensor1_end.second == 0

    # Start = 21:59:00
    assert sensor2_start.hour == 21
    assert sensor2_start.minute == 59
    assert sensor2_start.second == 0

    # End = 00:00:00
    assert sensor2_end.hour == 0
    assert sensor2_end.minute == 0
    assert sensor2_end.second == 0


async def test_measure(hass):
    """Test the history values sensor measure."""
    now = dt_util.utcnow()
    start_time = now - timedelta(minutes=60)
    start = '{{{{ {} }}}}'.format(dt_util.as_timestamp(start_time))
    end = '{{{{ {} }}}}'.format(dt_util.as_timestamp(now))

    t_0 = start_time + timedelta(minutes=20)
    t_1 = t_0 + timedelta(minutes=20)
    t_2 = t_1 + timedelta(minutes=10)

    # Start     t0        t1        t2        End
    # |--20min--|--20min--|--10min--|--10min--|
    # |---10----|---20----|---15----|----9----|

    fake_states = {
        'sensor.test_target': [
            ha.State('sensor.test_target', '10', last_changed=start_time),
            ha.State('sensor.test_target', '20', last_changed=t_0),
            ha.State('sensor.test_target', '15', last_changed=t_1),
            ha.State('sensor.test_target', '9', last_changed=t_2),
        ]
    }
    await async_init_recorder(hass)
    hass.states.async_set('sensor.test_target', 9)

    with patch('homeassistant.components.history.'
               'state_changes_during_period', return_value=fake_states):
        with assert_setup_component(5, SENSOR_DOMAIN):
            await async_setup_component(
                hass, SENSOR_DOMAIN, {
                    'sensor': [{
                        'platform': HVS_DOMAIN,
                        'name': 'Test Sensor 1',
                        'type': TYPE_LOW,
                        'target_entity_id': 'sensor.test_target',
                        'start': start,
                        'end': end,
                    }, {
                        'platform': HVS_DOMAIN,
                        'name': 'Test Sensor 2',
                        'type': TYPE_PEAK,
                        'target_entity_id': 'sensor.test_target',
                        'start': start,
                        'end': end,
                    }, {
                        'platform': HVS_DOMAIN,
                        'name': 'Test Sensor 3',
                        'type': TYPE_RANGE,
                        'target_entity_id': 'sensor.test_target',
                        'start': start,
                        'end': end,
                    }, {
                        'platform': HVS_DOMAIN,
                        'name': 'Test Sensor 4',
                        'type': TYPE_AVG,
                        'target_entity_id': 'sensor.test_target',
                        'start': start,
                        'end': end,
                    }, {
                        'platform': HVS_DOMAIN,
                        'name': 'Test Sensor 5',
                        'type': TYPE_LOW,
                        'target_entity_id': 'unknown.test_target',
                        'start': start,
                        'end': end,
                    }]
                })

    states = []
    for sensor in ['sensor.test_sensor_1', 'sensor.test_sensor_2',
                   'sensor.test_sensor_3', 'sensor.test_sensor_4',
                   'sensor.test_sensor_5']:
        states.append(hass.states.get(sensor))

    assert float(states[0].state) == 9
    assert float(states[1].state) == 20
    assert float(states[2].state) == 11
    assert float(states[3].state) == 14
    assert states[4].state == STATE_UNKNOWN


async def test_wrong_date(hass):
    """Test when start or end value is not a timestamp or a date."""
    good = Template('{{ now() }}', hass)
    bad = Template('{{ TEST }}', hass)

    sensor1 = HistoryValuesSensor(
        'Test', 'sensor.test_sensor_1', TYPE_PEAK, 'sensor.test_target', None,
        good, bad, None, None)
    sensor2 = HistoryValuesSensor(
        'Test', 'sensor.test_sensor_2', TYPE_PEAK, 'sensor.test_target', None,
        bad, good, None, None)

    # pylint: disable=protected-access
    before_update1 = sensor1._period
    before_update2 = sensor2._period

    await asyncio.gather(sensor1.update_period(), sensor2.update_period())

    assert before_update1 == sensor1._period
    assert before_update2 == sensor2._period


async def test_bad_template(hass):
    """Test Exception when the template cannot be parsed."""
    bad = Template('{{ x - 12 }}', hass)  # x is undefined
    duration = '01:00'

    sensor1 = HistoryValuesSensor(
        'Test', 'sensor.test_sensor_1', TYPE_PEAK, 'sensor.test_target', None,
        bad, None, duration, None)
    sensor2 = HistoryValuesSensor(
        'Test', 'sensor.test_sensor_2', TYPE_PEAK, 'sensor.test_target', None,
        None, bad, duration, None)

    # pylint: disable=protected-access
    before_update1 = sensor1._period
    before_update2 = sensor2._period

    await asyncio.gather(sensor1.update_period(), sensor2.update_period())

    assert before_update1 == sensor1._period
    assert before_update2 == sensor2._period


async def test_precision_parsing(hass):
    """Test parsing of float precision values."""
    today = Template('{{ now().replace(hour=0).replace(minute=0)'
                     '.replace(second=0) }}', hass)
    duration = timedelta(hours=2, minutes=1)

    sensor1 = HistoryValuesSensor(
        'test', 'sensor.test_sensor', TYPE_PEAK, 'sensor.test_target', None,
        today, None, duration, None)

    assert sensor1.get_precision(-5.1) == 1
    assert sensor1.get_precision(23) == 0
    assert sensor1.get_precision(0.123) == 3
    assert sensor1.get_precision(1.444555, 3) == 3
    assert sensor1.get_precision(1.1234567890123) == 10
