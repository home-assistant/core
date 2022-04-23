"""The test for the History Statistics sensor platform."""
# pylint: disable=protected-access
from datetime import datetime, timedelta
import unittest
from unittest.mock import patch

from freezegun import freeze_time
import pytest

from homeassistant import config as hass_config
from homeassistant.components.history_stats import DOMAIN
from homeassistant.components.history_stats.sensor import HistoryStatsSensor
from homeassistant.const import SERVICE_RELOAD, STATE_UNKNOWN
import homeassistant.core as ha
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.helpers.template import Template
from homeassistant.setup import async_setup_component, setup_component
import homeassistant.util.dt as dt_util

from tests.common import (
    async_fire_time_changed,
    get_fixture_path,
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
        now = datetime(2019, 1, 1, 23, 30, 0, tzinfo=dt_util.UTC)
        with patch("homeassistant.util.dt.now", return_value=now):
            today = Template(
                "{{ now().replace(hour=0).replace(minute=0).replace(second=0) }}",
                self.hass,
            )
            duration = timedelta(hours=2, minutes=1)

            sensor1 = HistoryStatsSensor(
                "test", "on", today, None, duration, "time", "test"
            )
            sensor1.hass = self.hass
            sensor2 = HistoryStatsSensor(
                "test", "on", None, today, duration, "time", "test"
            )
            sensor2.hass = self.hass

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

        sensor1 = HistoryStatsSensor("test", "on", good, bad, None, "time", "Test")
        sensor1.hass = self.hass
        sensor2 = HistoryStatsSensor("test", "on", bad, good, None, "time", "Test")
        sensor2.hass = self.hass

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

        sensor1 = HistoryStatsSensor("test", "on", bad, None, duration, "time", "Test")
        sensor1.hass = self.hass
        sensor2 = HistoryStatsSensor("test", "on", None, bad, duration, "time", "Test")
        sensor2.hass = self.hass

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


async def test_reload(hass, recorder_mock):
    """Verify we can reload history_stats sensors."""
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

    yaml_path = get_fixture_path("configuration.yaml", "history_stats")
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


async def test_measure_multiple(hass, recorder_mock):
    """Test the history statistics sensor measure for multiple ."""
    start_time = dt_util.utcnow() - timedelta(minutes=60)
    t0 = start_time + timedelta(minutes=20)
    t1 = t0 + timedelta(minutes=10)
    t2 = t1 + timedelta(minutes=10)

    # Start     t0        t1        t2        End
    # |--20min--|--20min--|--10min--|--10min--|
    # |---------|--orange-|-default-|---blue--|

    def _fake_states(*args, **kwargs):
        return {
            "input_select.test_id": [
                # Because we use include_start_time_state we need to mock
                # value at start
                ha.State("input_select.test_id", "", last_changed=start_time),
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
        "homeassistant.components.recorder.history.state_changes_during_period",
        _fake_states,
    ):
        for i in range(1, 5):
            await async_update_entity(hass, f"sensor.sensor{i}")
        await hass.async_block_till_done()

    assert hass.states.get("sensor.sensor1").state == "0.5"
    assert hass.states.get("sensor.sensor2").state == STATE_UNKNOWN
    assert hass.states.get("sensor.sensor3").state == "2"
    assert hass.states.get("sensor.sensor4").state == "50.0"


async def async_test_measure(hass, recorder_mock):
    """Test the history statistics sensor measure."""
    start_time = dt_util.utcnow() - timedelta(minutes=60)
    t0 = start_time + timedelta(minutes=20)
    t1 = t0 + timedelta(minutes=10)
    t2 = t1 + timedelta(minutes=10)

    # Start     t0        t1        t2        End
    # |--20min--|--20min--|--10min--|--10min--|
    # |---off---|---on----|---off---|---on----|

    def _fake_states(*args, **kwargs):
        return {
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
        "homeassistant.components.recorder.history.state_changes_during_period",
        _fake_states,
    ):
        for i in range(1, 5):
            await async_update_entity(hass, f"sensor.sensor{i}")
        await hass.async_block_till_done()

    assert hass.states.get("sensor.sensor1").state == "0.5"
    assert hass.states.get("sensor.sensor2").state == STATE_UNKNOWN
    assert hass.states.get("sensor.sensor3").state == "2"
    assert hass.states.get("sensor.sensor4").state == "50.0"


async def test_async_on_entire_period(hass, recorder_mock):
    """Test the history statistics sensor measuring as on the entire period."""
    start_time = dt_util.utcnow() - timedelta(minutes=60)
    t0 = start_time + timedelta(minutes=20)
    t1 = t0 + timedelta(minutes=10)
    t2 = t1 + timedelta(minutes=10)

    # Start     t0        t1        t2        End
    # |--20min--|--20min--|--10min--|--10min--|
    # |---on----|--off----|---on----|--off----|

    def _fake_states(*args, **kwargs):
        return {
            "binary_sensor.test_on_id": [
                ha.State("binary_sensor.test_on_id", "on", last_changed=start_time),
                ha.State("binary_sensor.test_on_id", "on", last_changed=t0),
                ha.State("binary_sensor.test_on_id", "on", last_changed=t1),
                ha.State("binary_sensor.test_on_id", "on", last_changed=t2),
            ]
        }

    await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {
                    "platform": "history_stats",
                    "entity_id": "binary_sensor.test_on_id",
                    "name": "on_sensor1",
                    "state": "on",
                    "start": "{{ as_timestamp(now()) - 3600 }}",
                    "end": "{{ now() }}",
                    "type": "time",
                },
                {
                    "platform": "history_stats",
                    "entity_id": "binary_sensor.test_on_id",
                    "name": "on_sensor2",
                    "state": "on",
                    "start": "{{ as_timestamp(now()) - 3600 }}",
                    "end": "{{ now() }}",
                    "type": "time",
                },
                {
                    "platform": "history_stats",
                    "entity_id": "binary_sensor.test_on_id",
                    "name": "on_sensor3",
                    "state": "on",
                    "start": "{{ as_timestamp(now()) - 3600 }}",
                    "end": "{{ now() }}",
                    "type": "count",
                },
                {
                    "platform": "history_stats",
                    "entity_id": "binary_sensor.test_on_id",
                    "name": "on_sensor4",
                    "state": "on",
                    "start": "{{ as_timestamp(now()) - 3600 }}",
                    "end": "{{ now() }}",
                    "type": "ratio",
                },
            ]
        },
    )

    with patch(
        "homeassistant.components.recorder.history.state_changes_during_period",
        _fake_states,
    ):
        for i in range(1, 5):
            await async_update_entity(hass, f"sensor.on_sensor{i}")
        await hass.async_block_till_done()

    assert hass.states.get("sensor.on_sensor1").state == "1.0"
    assert hass.states.get("sensor.on_sensor2").state == "1.0"
    assert hass.states.get("sensor.on_sensor3").state == "0"
    assert hass.states.get("sensor.on_sensor4").state == "100.0"


async def test_async_off_entire_period(hass, recorder_mock):
    """Test the history statistics sensor measuring as off the entire period."""
    start_time = dt_util.utcnow() - timedelta(minutes=60)
    t0 = start_time + timedelta(minutes=20)
    t1 = t0 + timedelta(minutes=10)
    t2 = t1 + timedelta(minutes=10)

    # Start     t0        t1        t2        End
    # |--20min--|--20min--|--10min--|--10min--|
    # |---off----|--off----|---off----|--off----|

    def _fake_states(*args, **kwargs):
        return {
            "binary_sensor.test_on_id": [
                ha.State("binary_sensor.test_on_id", "off", last_changed=start_time),
                ha.State("binary_sensor.test_on_id", "off", last_changed=t0),
                ha.State("binary_sensor.test_on_id", "off", last_changed=t1),
                ha.State("binary_sensor.test_on_id", "off", last_changed=t2),
            ]
        }

    await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {
                    "platform": "history_stats",
                    "entity_id": "binary_sensor.test_on_id",
                    "name": "on_sensor1",
                    "state": "on",
                    "start": "{{ as_timestamp(now()) - 3600 }}",
                    "end": "{{ now() }}",
                    "type": "time",
                },
                {
                    "platform": "history_stats",
                    "entity_id": "binary_sensor.test_on_id",
                    "name": "on_sensor2",
                    "state": "on",
                    "start": "{{ as_timestamp(now()) - 3600 }}",
                    "end": "{{ now() }}",
                    "type": "time",
                },
                {
                    "platform": "history_stats",
                    "entity_id": "binary_sensor.test_on_id",
                    "name": "on_sensor3",
                    "state": "on",
                    "start": "{{ as_timestamp(now()) - 3600 }}",
                    "end": "{{ now() }}",
                    "type": "count",
                },
                {
                    "platform": "history_stats",
                    "entity_id": "binary_sensor.test_on_id",
                    "name": "on_sensor4",
                    "state": "on",
                    "start": "{{ as_timestamp(now()) - 3600 }}",
                    "end": "{{ now() }}",
                    "type": "ratio",
                },
            ]
        },
    )

    with patch(
        "homeassistant.components.recorder.history.state_changes_during_period",
        _fake_states,
    ):
        for i in range(1, 5):
            await async_update_entity(hass, f"sensor.on_sensor{i}")
        await hass.async_block_till_done()

    assert hass.states.get("sensor.on_sensor1").state == "0.0"
    assert hass.states.get("sensor.on_sensor2").state == "0.0"
    assert hass.states.get("sensor.on_sensor3").state == "0"
    assert hass.states.get("sensor.on_sensor4").state == "0.0"


async def test_async_start_from_history_and_switch_to_watching_state_changes_single(
    hass,
    recorder_mock,
):
    """Test we startup from history and switch to watching state changes."""
    hass.config.set_time_zone("UTC")
    utcnow = dt_util.utcnow()
    start_time = utcnow.replace(hour=0, minute=0, second=0, microsecond=0)

    # Start     t0        t1        t2       Startup                                       End
    # |--20min--|--20min--|--10min--|--10min--|---------30min---------|---15min--|---15min--|
    # |---on----|---on----|---on----|---on----|----------on-----------|---off----|----on----|

    def _fake_states(*args, **kwargs):
        return {
            "binary_sensor.state": [
                ha.State(
                    "binary_sensor.state",
                    "on",
                    last_changed=start_time,
                    last_updated=start_time,
                ),
            ]
        }

    with patch(
        "homeassistant.components.recorder.history.state_changes_during_period",
        _fake_states,
    ):

        with freeze_time(start_time):
            await async_setup_component(
                hass,
                "sensor",
                {
                    "sensor": [
                        {
                            "platform": "history_stats",
                            "entity_id": "binary_sensor.state",
                            "name": "sensor1",
                            "state": "on",
                            "start": "{{ utcnow().replace(hour=0, minute=0, second=0) }}",
                            "duration": {"hours": 2},
                            "type": "time",
                        }
                    ]
                },
            )

            await async_update_entity(hass, "sensor.sensor1")
            await hass.async_block_till_done()

    assert hass.states.get("sensor.sensor1").state == "0.0"

    one_hour_in = start_time + timedelta(minutes=60)
    with freeze_time(one_hour_in):
        async_fire_time_changed(hass, one_hour_in)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.sensor1").state == "1.0"

    turn_off_time = start_time + timedelta(minutes=90)
    with freeze_time(turn_off_time):
        hass.states.async_set("binary_sensor.state", "off")
        await hass.async_block_till_done()
        async_fire_time_changed(hass, turn_off_time)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.sensor1").state == "1.5"

    turn_back_on_time = start_time + timedelta(minutes=105)
    with freeze_time(turn_back_on_time):
        async_fire_time_changed(hass, turn_back_on_time)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.sensor1").state == "1.5"

    with freeze_time(turn_back_on_time):
        hass.states.async_set("binary_sensor.state", "on")
        await hass.async_block_till_done()

    assert hass.states.get("sensor.sensor1").state == "1.5"

    end_time = start_time + timedelta(minutes=120)
    with freeze_time(end_time):
        async_fire_time_changed(hass, end_time)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.sensor1").state == "1.75"


async def test_async_start_from_history_and_switch_to_watching_state_changes_single_expanding_window(
    hass,
    recorder_mock,
):
    """Test we startup from history and switch to watching state changes with an expanding end time."""
    hass.config.set_time_zone("UTC")
    utcnow = dt_util.utcnow()
    start_time = utcnow.replace(hour=0, minute=0, second=0, microsecond=0)

    # Start     t0        t1        t2       Startup                                       End
    # |--20min--|--20min--|--10min--|--10min--|---------30min---------|---15min--|---15min--|
    # |---on----|---on----|---on----|---on----|----------on-----------|---off----|----on----|

    def _fake_states(*args, **kwargs):
        return {
            "binary_sensor.state": [
                ha.State(
                    "binary_sensor.state",
                    "on",
                    last_changed=start_time,
                    last_updated=start_time,
                ),
            ]
        }

    with patch(
        "homeassistant.components.recorder.history.state_changes_during_period",
        _fake_states,
    ):

        with freeze_time(start_time):
            await async_setup_component(
                hass,
                "sensor",
                {
                    "sensor": [
                        {
                            "platform": "history_stats",
                            "entity_id": "binary_sensor.state",
                            "name": "sensor1",
                            "state": "on",
                            "start": "{{ utcnow().replace(hour=0, minute=0, second=0) }}",
                            "end": "{{ utcnow() }}",
                            "type": "time",
                        }
                    ]
                },
            )

            await async_update_entity(hass, "sensor.sensor1")
            await hass.async_block_till_done()

    assert hass.states.get("sensor.sensor1").state == "0.0"

    one_hour_in = start_time + timedelta(minutes=60)
    with freeze_time(one_hour_in):
        async_fire_time_changed(hass, one_hour_in)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.sensor1").state == "1.0"

    turn_off_time = start_time + timedelta(minutes=90)
    with freeze_time(turn_off_time):
        hass.states.async_set("binary_sensor.state", "off")
        await hass.async_block_till_done()
        async_fire_time_changed(hass, turn_off_time)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.sensor1").state == "1.5"

    turn_back_on_time = start_time + timedelta(minutes=105)
    with freeze_time(turn_back_on_time):
        async_fire_time_changed(hass, turn_back_on_time)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.sensor1").state == "1.5"

    with freeze_time(turn_back_on_time):
        hass.states.async_set("binary_sensor.state", "on")
        await hass.async_block_till_done()

    assert hass.states.get("sensor.sensor1").state == "1.5"

    end_time = start_time + timedelta(minutes=120)
    with freeze_time(end_time):
        async_fire_time_changed(hass, end_time)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.sensor1").state == "1.75"


async def test_async_start_from_history_and_switch_to_watching_state_changes_multiple(
    hass,
    recorder_mock,
):
    """Test we startup from history and switch to watching state changes."""
    hass.config.set_time_zone("UTC")
    utcnow = dt_util.utcnow()
    start_time = utcnow.replace(hour=0, minute=0, second=0, microsecond=0)

    # Start     t0        t1        t2       Startup                                       End
    # |--20min--|--20min--|--10min--|--10min--|---------30min---------|---15min--|---15min--|
    # |---on----|---on----|---on----|---on----|----------on-----------|---off----|----on----|

    def _fake_states(*args, **kwargs):
        return {
            "binary_sensor.state": [
                ha.State(
                    "binary_sensor.state",
                    "on",
                    last_changed=start_time,
                    last_updated=start_time,
                ),
            ]
        }

    with patch(
        "homeassistant.components.recorder.history.state_changes_during_period",
        _fake_states,
    ):

        with freeze_time(start_time):
            await async_setup_component(
                hass,
                "sensor",
                {
                    "sensor": [
                        {
                            "platform": "history_stats",
                            "entity_id": "binary_sensor.state",
                            "name": "sensor1",
                            "state": "on",
                            "start": "{{ utcnow().replace(hour=0, minute=0, second=0) }}",
                            "duration": {"hours": 2},
                            "type": "time",
                        },
                        {
                            "platform": "history_stats",
                            "entity_id": "binary_sensor.state",
                            "name": "sensor2",
                            "state": "on",
                            "start": "{{ utcnow().replace(hour=0, minute=0, second=0) }}",
                            "duration": {"hours": 2},
                            "type": "time",
                        },
                        {
                            "platform": "history_stats",
                            "entity_id": "binary_sensor.state",
                            "name": "sensor3",
                            "state": "on",
                            "start": "{{ utcnow().replace(hour=0, minute=0, second=0) }}",
                            "duration": {"hours": 2},
                            "type": "count",
                        },
                        {
                            "platform": "history_stats",
                            "entity_id": "binary_sensor.state",
                            "name": "sensor4",
                            "state": "on",
                            "start": "{{ utcnow().replace(hour=0, minute=0, second=0) }}",
                            "duration": {"hours": 2},
                            "type": "ratio",
                        },
                    ]
                },
            )
            for i in range(1, 5):
                await async_update_entity(hass, f"sensor.sensor{i}")
            await hass.async_block_till_done()

    assert hass.states.get("sensor.sensor1").state == "0.0"
    assert hass.states.get("sensor.sensor2").state == "0.0"
    assert hass.states.get("sensor.sensor3").state == "0"
    assert hass.states.get("sensor.sensor4").state == "0.0"

    one_hour_in = start_time + timedelta(minutes=60)
    with freeze_time(one_hour_in):
        async_fire_time_changed(hass, one_hour_in)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.sensor1").state == "1.0"
    assert hass.states.get("sensor.sensor2").state == "1.0"
    assert hass.states.get("sensor.sensor3").state == "0"
    assert hass.states.get("sensor.sensor4").state == "50.0"

    turn_off_time = start_time + timedelta(minutes=90)
    with freeze_time(turn_off_time):
        hass.states.async_set("binary_sensor.state", "off")
        await hass.async_block_till_done()
        async_fire_time_changed(hass, turn_off_time)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.sensor1").state == "1.5"
    assert hass.states.get("sensor.sensor2").state == "1.5"
    assert hass.states.get("sensor.sensor3").state == "0"
    assert hass.states.get("sensor.sensor4").state == "75.0"

    turn_back_on_time = start_time + timedelta(minutes=105)
    with freeze_time(turn_back_on_time):
        async_fire_time_changed(hass, turn_back_on_time)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.sensor1").state == "1.5"
    assert hass.states.get("sensor.sensor2").state == "1.5"
    assert hass.states.get("sensor.sensor3").state == "0"
    assert hass.states.get("sensor.sensor4").state == "75.0"

    with freeze_time(turn_back_on_time):
        hass.states.async_set("binary_sensor.state", "on")
        await hass.async_block_till_done()

    assert hass.states.get("sensor.sensor1").state == "1.5"
    assert hass.states.get("sensor.sensor2").state == "1.5"
    assert hass.states.get("sensor.sensor3").state == "1"
    assert hass.states.get("sensor.sensor4").state == "75.0"

    end_time = start_time + timedelta(minutes=120)
    with freeze_time(end_time):
        async_fire_time_changed(hass, end_time)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.sensor1").state == "1.75"
    assert hass.states.get("sensor.sensor2").state == "1.75"
    assert hass.states.get("sensor.sensor3").state == "1"
    assert hass.states.get("sensor.sensor4").state == "87.5"


async def test_does_not_work_into_the_future(hass, recorder_mock):
    """Test history cannot tell the future.

    Verifies we do not regress https://github.com/home-assistant/core/pull/20589
    """
    hass.config.set_time_zone("UTC")
    utcnow = dt_util.utcnow()
    start_time = utcnow.replace(hour=0, minute=0, second=0, microsecond=0)

    # Start     t0        t1        t2       Startup                                       End
    # |--20min--|--20min--|--10min--|--10min--|---------30min---------|---15min--|---15min--|
    # |---on----|---on----|---on----|---on----|----------on-----------|---off----|----on----|

    def _fake_states(*args, **kwargs):
        return {
            "binary_sensor.state": [
                ha.State(
                    "binary_sensor.state",
                    "on",
                    last_changed=start_time,
                    last_updated=start_time,
                ),
            ]
        }

    with patch(
        "homeassistant.components.recorder.history.state_changes_during_period",
        _fake_states,
    ):

        with freeze_time(start_time):
            await async_setup_component(
                hass,
                "sensor",
                {
                    "sensor": [
                        {
                            "platform": "history_stats",
                            "entity_id": "binary_sensor.state",
                            "name": "sensor1",
                            "state": "on",
                            "start": "{{ utcnow().replace(hour=23, minute=0, second=0) }}",
                            "duration": {"hours": 1},
                            "type": "time",
                        }
                    ]
                },
            )

            await async_update_entity(hass, "sensor.sensor1")
            await hass.async_block_till_done()

        assert hass.states.get("sensor.sensor1").state == STATE_UNKNOWN

        one_hour_in = start_time + timedelta(minutes=60)
        with freeze_time(one_hour_in):
            async_fire_time_changed(hass, one_hour_in)
            await hass.async_block_till_done()

        assert hass.states.get("sensor.sensor1").state == STATE_UNKNOWN

        turn_off_time = start_time + timedelta(minutes=90)
        with freeze_time(turn_off_time):
            hass.states.async_set("binary_sensor.state", "off")
            await hass.async_block_till_done()
            async_fire_time_changed(hass, turn_off_time)
            await hass.async_block_till_done()

        assert hass.states.get("sensor.sensor1").state == STATE_UNKNOWN

        turn_back_on_time = start_time + timedelta(minutes=105)
        with freeze_time(turn_back_on_time):
            async_fire_time_changed(hass, turn_back_on_time)
            await hass.async_block_till_done()

        assert hass.states.get("sensor.sensor1").state == STATE_UNKNOWN

        with freeze_time(turn_back_on_time):
            hass.states.async_set("binary_sensor.state", "on")
            await hass.async_block_till_done()

        assert hass.states.get("sensor.sensor1").state == STATE_UNKNOWN

        end_time = start_time + timedelta(minutes=120)
        with freeze_time(end_time):
            async_fire_time_changed(hass, end_time)
            await hass.async_block_till_done()

        assert hass.states.get("sensor.sensor1").state == STATE_UNKNOWN

        in_the_window = start_time + timedelta(hours=23, minutes=5)
        with freeze_time(in_the_window):
            async_fire_time_changed(hass, in_the_window)
            await hass.async_block_till_done()

        assert hass.states.get("sensor.sensor1").state == "0.08"

    past_the_window = start_time + timedelta(hours=25)
    with patch(
        "homeassistant.components.recorder.history.state_changes_during_period",
        return_value=[],
    ), freeze_time(past_the_window):
        async_fire_time_changed(hass, past_the_window)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.sensor1").state == STATE_UNKNOWN

    def _fake_off_states(*args, **kwargs):
        return {
            "binary_sensor.state": [
                ha.State(
                    "binary_sensor.state",
                    "off",
                    last_changed=start_time,
                    last_updated=start_time,
                ),
            ]
        }

    past_the_window_with_data = start_time + timedelta(hours=26)
    with patch(
        "homeassistant.components.recorder.history.state_changes_during_period",
        _fake_off_states,
    ), freeze_time(past_the_window_with_data):
        async_fire_time_changed(hass, past_the_window_with_data)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.sensor1").state == STATE_UNKNOWN

    at_the_next_window_with_data = start_time + timedelta(days=1, hours=23)
    with patch(
        "homeassistant.components.recorder.history.state_changes_during_period",
        _fake_off_states,
    ), freeze_time(at_the_next_window_with_data):
        async_fire_time_changed(hass, at_the_next_window_with_data)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.sensor1").state == "0.0"
