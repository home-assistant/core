"""The test for the History Statistics sensor platform."""
# pylint: disable=protected-access
from datetime import datetime, timedelta
from os import path
import unittest
from unittest.mock import patch

import pytest
import pytz

from homeassistant import config as hass_config
from homeassistant.components.history_stats import DOMAIN
from homeassistant.components.history_stats.sensor import HistoryStatsSensor
from homeassistant.const import SERVICE_RELOAD, STATE_UNKNOWN
import homeassistant.core as ha
from homeassistant.helpers.template import Template
from homeassistant.setup import async_setup_component, setup_component
import homeassistant.util.dt as dt_util

from tests.common import (
    async_init_recorder_component,
    get_test_home_assistant,
    init_recorder_component,
)


class TestHistoryStatsSensor(unittest.TestCase):
    """Test the History Statistics sensor."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.addCleanup(self.hass.stop)

    def test_setup(self):
        """Test the history statistics sensor setup."""
        self.init_recorder()
        config = {
            "history": {},
            "sensor": {
                "platform": "history_stats",
                "entity_id": "binary_sensor.test_id",
                "state": "on",
                "start": "{{ now().replace(hour=0)"
                ".replace(minute=0).replace(second=0) }}",
                "duration": "02:00",
                "name": "Test",
            },
        }

        assert setup_component(self.hass, "sensor", config)
        self.hass.block_till_done()

        state = self.hass.states.get("sensor.test")
        assert state.state == STATE_UNKNOWN

    def test_setup_multiple_states(self):
        """Test the history statistics sensor setup for multiple states."""
        self.init_recorder()
        config = {
            "history": {},
            "sensor": {
                "platform": "history_stats",
                "entity_id": "binary_sensor.test_id",
                "state": ["on", "true"],
                "start": "{{ now().replace(hour=0)"
                ".replace(minute=0).replace(second=0) }}",
                "duration": "02:00",
                "name": "Test",
            },
        }

        assert setup_component(self.hass, "sensor", config)
        self.hass.block_till_done()

        state = self.hass.states.get("sensor.test")
        assert state.state == STATE_UNKNOWN

    @patch(
        "homeassistant.helpers.template.TemplateEnvironment.is_safe_callable",
        return_value=True,
    )
    def test_period_parsing(self, mock):
        """Test the conversion from templates to period."""
        now = datetime(2019, 1, 1, 23, 30, 0, tzinfo=pytz.utc)
        with patch("homeassistant.util.dt.now", return_value=now):
            today = Template(
                "{{ now().replace(hour=0).replace(minute=0).replace(second=0) }}",
                self.hass,
            )
            duration = timedelta(hours=2, minutes=1)

            sensor1 = HistoryStatsSensor(
                self.hass, "test", "on", today, None, duration, "time", "test"
            )
            sensor2 = HistoryStatsSensor(
                self.hass, "test", "on", None, today, duration, "time", "test"
            )

            sensor1.update_period()
            sensor1_start, sensor1_end = sensor1._period
            sensor2.update_period()
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

    def test_wrong_date(self):
        """Test when start or end value is not a timestamp or a date."""
        good = Template("{{ now() }}", self.hass)
        bad = Template("{{ TEST }}", self.hass)

        sensor1 = HistoryStatsSensor(
            self.hass, "test", "on", good, bad, None, "time", "Test"
        )
        sensor2 = HistoryStatsSensor(
            self.hass, "test", "on", bad, good, None, "time", "Test"
        )

        before_update1 = sensor1._period
        before_update2 = sensor2._period

        sensor1.update_period()
        sensor2.update_period()

        assert before_update1 == sensor1._period
        assert before_update2 == sensor2._period

    def test_wrong_duration(self):
        """Test when duration value is not a timedelta."""
        self.init_recorder()
        config = {
            "history": {},
            "sensor": {
                "platform": "history_stats",
                "entity_id": "binary_sensor.test_id",
                "name": "Test",
                "state": "on",
                "start": "{{ now() }}",
                "duration": "TEST",
            },
        }

        setup_component(self.hass, "sensor", config)
        assert self.hass.states.get("sensor.test") is None
        with pytest.raises(TypeError):
            setup_component(self.hass, "sensor", config)()

    def test_bad_template(self):
        """Test Exception when the template cannot be parsed."""
        bad = Template("{{ x - 12 }}", self.hass)  # x is undefined
        duration = "01:00"

        sensor1 = HistoryStatsSensor(
            self.hass, "test", "on", bad, None, duration, "time", "Test"
        )
        sensor2 = HistoryStatsSensor(
            self.hass, "test", "on", None, bad, duration, "time", "Test"
        )

        before_update1 = sensor1._period
        before_update2 = sensor2._period

        sensor1.update_period()
        sensor2.update_period()

        assert before_update1 == sensor1._period
        assert before_update2 == sensor2._period

    def test_not_enough_arguments(self):
        """Test config when not enough arguments provided."""
        self.init_recorder()
        config = {
            "history": {},
            "sensor": {
                "platform": "history_stats",
                "entity_id": "binary_sensor.test_id",
                "name": "Test",
                "state": "on",
                "start": "{{ now() }}",
            },
        }

        setup_component(self.hass, "sensor", config)
        assert self.hass.states.get("sensor.test") is None
        with pytest.raises(TypeError):
            setup_component(self.hass, "sensor", config)()

    def test_too_many_arguments(self):
        """Test config when too many arguments provided."""
        self.init_recorder()
        config = {
            "history": {},
            "sensor": {
                "platform": "history_stats",
                "entity_id": "binary_sensor.test_id",
                "name": "Test",
                "state": "on",
                "start": "{{ as_timestamp(now()) - 3600 }}",
                "end": "{{ now() }}",
                "duration": "01:00",
            },
        }

        setup_component(self.hass, "sensor", config)
        assert self.hass.states.get("sensor.test") is None
        with pytest.raises(TypeError):
            setup_component(self.hass, "sensor", config)()

    def init_recorder(self):
        """Initialize the recorder."""
        init_recorder_component(self.hass)
        self.hass.start()


async def test_reload(hass):
    """Verify we can reload history_stats sensors."""
    await async_init_recorder_component(hass)

    hass.state = ha.CoreState.not_running
    hass.states.async_set("binary_sensor.test_id", "on")

    await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": {
                "platform": "history_stats",
                "entity_id": "binary_sensor.test_id",
                "name": "test",
                "state": "on",
                "start": "{{ as_timestamp(now()) - 3600 }}",
                "duration": "01:00",
            },
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2

    assert hass.states.get("sensor.test")

    yaml_path = path.join(
        _get_fixtures_base_path(),
        "fixtures",
        "history_stats/configuration.yaml",
    )
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2

    assert hass.states.get("sensor.test") is None
    assert hass.states.get("sensor.second_test")


async def test_measure_multiple(hass):
    """Test the history statistics sensor measure for multiple ."""
    await async_init_recorder_component(hass)

    t0 = dt_util.utcnow() - timedelta(minutes=40)
    t1 = t0 + timedelta(minutes=20)
    t2 = dt_util.utcnow() - timedelta(minutes=10)

    # Start     t0        t1        t2        End
    # |--20min--|--20min--|--10min--|--10min--|
    # |---------|--orange-|-default-|---blue--|

    fake_states = {
        "input_select.test_id": [
            ha.State("input_select.test_id", "orange", last_changed=t0),
            ha.State("input_select.test_id", "default", last_changed=t1),
            ha.State("input_select.test_id", "blue", last_changed=t2),
        ]
    }

    await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {
                    "platform": "history_stats",
                    "entity_id": "input_select.test_id",
                    "name": "sensor1",
                    "state": ["orange", "blue"],
                    "start": "{{ as_timestamp(now()) - 3600 }}",
                    "end": "{{ now() }}",
                    "type": "time",
                },
                {
                    "platform": "history_stats",
                    "entity_id": "unknown.test_id",
                    "name": "sensor2",
                    "state": ["orange", "blue"],
                    "start": "{{ as_timestamp(now()) - 3600 }}",
                    "end": "{{ now() }}",
                    "type": "time",
                },
                {
                    "platform": "history_stats",
                    "entity_id": "input_select.test_id",
                    "name": "sensor3",
                    "state": ["orange", "blue"],
                    "start": "{{ as_timestamp(now()) - 3600 }}",
                    "end": "{{ now() }}",
                    "type": "count",
                },
                {
                    "platform": "history_stats",
                    "entity_id": "input_select.test_id",
                    "name": "sensor4",
                    "state": ["orange", "blue"],
                    "start": "{{ as_timestamp(now()) - 3600 }}",
                    "end": "{{ now() }}",
                    "type": "ratio",
                },
            ]
        },
    )

    with patch(
        "homeassistant.components.history.state_changes_during_period",
        return_value=fake_states,
    ), patch("homeassistant.components.history.get_state", return_value=None):
        for i in range(1, 5):
            await hass.helpers.entity_component.async_update_entity(f"sensor.sensor{i}")
        await hass.async_block_till_done()

    assert hass.states.get("sensor.sensor1").state == "0.5"
    assert hass.states.get("sensor.sensor2").state == STATE_UNKNOWN
    assert hass.states.get("sensor.sensor3").state == "2"
    assert hass.states.get("sensor.sensor4").state == "50.0"


async def async_test_measure(hass):
    """Test the history statistics sensor measure."""
    t0 = dt_util.utcnow() - timedelta(minutes=40)
    t1 = t0 + timedelta(minutes=20)
    t2 = dt_util.utcnow() - timedelta(minutes=10)

    # Start     t0        t1        t2        End
    # |--20min--|--20min--|--10min--|--10min--|
    # |---off---|---on----|---off---|---on----|

    fake_states = {
        "binary_sensor.test_id": [
            ha.State("binary_sensor.test_id", "on", last_changed=t0),
            ha.State("binary_sensor.test_id", "off", last_changed=t1),
            ha.State("binary_sensor.test_id", "on", last_changed=t2),
        ]
    }

    await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {
                    "platform": "history_stats",
                    "entity_id": "binary_sensor.test_id",
                    "name": "sensor1",
                    "state": "on",
                    "start": "{{ as_timestamp(now()) - 3600 }}",
                    "end": "{{ now() }}",
                    "type": "time",
                },
                {
                    "platform": "history_stats",
                    "entity_id": "binary_sensor.test_id",
                    "name": "sensor2",
                    "state": "on",
                    "start": "{{ as_timestamp(now()) - 3600 }}",
                    "end": "{{ now() }}",
                    "type": "time",
                },
                {
                    "platform": "history_stats",
                    "entity_id": "binary_sensor.test_id",
                    "name": "sensor3",
                    "state": "on",
                    "start": "{{ as_timestamp(now()) - 3600 }}",
                    "end": "{{ now() }}",
                    "type": "count",
                },
                {
                    "platform": "history_stats",
                    "entity_id": "binary_sensor.test_id",
                    "name": "sensor4",
                    "state": "on",
                    "start": "{{ as_timestamp(now()) - 3600 }}",
                    "end": "{{ now() }}",
                    "type": "ratio",
                },
            ]
        },
    )

    with patch(
        "homeassistant.components.history.state_changes_during_period",
        return_value=fake_states,
    ), patch("homeassistant.components.history.get_state", return_value=None):
        for i in range(1, 5):
            await hass.helpers.entity_component.async_update_entity(f"sensor.sensor{i}")
        await hass.async_block_till_done()

    assert hass.states.get("sensor.sensor1").state == "0.5"
    assert hass.states.get("sensor.sensor2").state == STATE_UNKNOWN
    assert hass.states.get("sensor.sensor3").state == "2"
    assert hass.states.get("sensor.sensor4").state == "50.0"


def _get_fixtures_base_path():
    return path.dirname(path.dirname(path.dirname(__file__)))
