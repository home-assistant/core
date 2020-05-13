"""Test Times of the Day Binary Sensor."""
from datetime import datetime, timedelta
import unittest

import pytz

from homeassistant import setup
from homeassistant.const import STATE_OFF, STATE_ON
import homeassistant.core as ha
from homeassistant.helpers.sun import get_astral_event_date, get_astral_event_next
from homeassistant.setup import setup_component
import homeassistant.util.dt as dt_util

from tests.async_mock import patch
from tests.common import assert_setup_component, get_test_home_assistant


class TestBinarySensorTod(unittest.TestCase):
    """Test for Binary sensor tod platform."""

    hass = None
    # pylint: disable=invalid-name

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.latitude = 50.27583
        self.hass.config.longitude = 18.98583

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup(self):
        """Test the setup."""
        config = {
            "binary_sensor": [
                {
                    "platform": "tod",
                    "name": "Early Morning",
                    "after": "sunrise",
                    "after_offset": "-02:00",
                    "before": "7:00",
                    "before_offset": "1:00",
                },
                {
                    "platform": "tod",
                    "name": "Morning",
                    "after": "sunrise",
                    "before": "12:00",
                },
            ]
        }
        with assert_setup_component(2):
            assert setup.setup_component(self.hass, "binary_sensor", config)

    def test_setup_no_sensors(self):
        """Test setup with no sensors."""
        with assert_setup_component(0):
            assert setup.setup_component(
                self.hass, "binary_sensor", {"binary_sensor": {"platform": "tod"}}
            )

    def test_in_period_on_start(self):
        """Test simple setting."""
        test_time = datetime(2019, 1, 10, 18, 43, 0, tzinfo=self.hass.config.time_zone)
        config = {
            "binary_sensor": [
                {
                    "platform": "tod",
                    "name": "Evening",
                    "after": "18:00",
                    "before": "22:00",
                }
            ]
        }
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=test_time,
        ):
            setup_component(self.hass, "binary_sensor", config)

        self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.evening")
        assert state.state == STATE_ON

    def test_midnight_turnover_before_midnight_inside_period(self):
        """Test midnight turnover setting before midnight inside period ."""
        test_time = datetime(2019, 1, 10, 22, 30, 0, tzinfo=self.hass.config.time_zone)
        config = {
            "binary_sensor": [
                {"platform": "tod", "name": "Night", "after": "22:00", "before": "5:00"}
            ]
        }
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=test_time,
        ):
            setup_component(self.hass, "binary_sensor", config)

        self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.night")
        assert state.state == STATE_ON

    def test_midnight_turnover_after_midnight_inside_period(self):
        """Test midnight turnover setting before midnight inside period ."""
        test_time = self.hass.config.time_zone.localize(
            datetime(2019, 1, 10, 21, 0, 0)
        ).astimezone(pytz.UTC)
        config = {
            "binary_sensor": [
                {"platform": "tod", "name": "Night", "after": "22:00", "before": "5:00"}
            ]
        }
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=test_time,
        ):
            setup_component(self.hass, "binary_sensor", config)

            state = self.hass.states.get("binary_sensor.night")
            assert state.state == STATE_OFF

            self.hass.block_till_done()

        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=test_time + timedelta(hours=1),
        ):

            self.hass.bus.fire(
                ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: test_time + timedelta(hours=1)}
            )

            self.hass.block_till_done()
            state = self.hass.states.get("binary_sensor.night")
            assert state.state == STATE_ON

    def test_midnight_turnover_before_midnight_outside_period(self):
        """Test midnight turnover setting before midnight outside period."""
        test_time = self.hass.config.time_zone.localize(
            datetime(2019, 1, 10, 20, 30, 0)
        ).astimezone(pytz.UTC)
        config = {
            "binary_sensor": [
                {"platform": "tod", "name": "Night", "after": "22:00", "before": "5:00"}
            ]
        }
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=test_time,
        ):
            setup_component(self.hass, "binary_sensor", config)

        self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.night")
        assert state.state == STATE_OFF

    def test_midnight_turnover_after_midnight_outside_period(self):
        """Test midnight turnover setting before midnight inside period ."""
        test_time = self.hass.config.time_zone.localize(
            datetime(2019, 1, 10, 20, 0, 0)
        ).astimezone(pytz.UTC)

        config = {
            "binary_sensor": [
                {"platform": "tod", "name": "Night", "after": "22:00", "before": "5:00"}
            ]
        }
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=test_time,
        ):
            setup_component(self.hass, "binary_sensor", config)

        self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.night")
        assert state.state == STATE_OFF

        switchover_time = self.hass.config.time_zone.localize(
            datetime(2019, 1, 11, 4, 59, 0)
        ).astimezone(pytz.UTC)
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=switchover_time,
        ):

            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: switchover_time})
            self.hass.block_till_done()
            state = self.hass.states.get("binary_sensor.night")
            assert state.state == STATE_ON

        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=switchover_time + timedelta(minutes=1, seconds=1),
        ):

            self.hass.bus.fire(
                ha.EVENT_TIME_CHANGED,
                {ha.ATTR_NOW: switchover_time + timedelta(minutes=1, seconds=1)},
            )

            self.hass.block_till_done()
            state = self.hass.states.get("binary_sensor.night")
            assert state.state == STATE_OFF

    def test_from_sunrise_to_sunset(self):
        """Test period from sunrise to sunset."""
        test_time = self.hass.config.time_zone.localize(
            datetime(2019, 1, 12)
        ).astimezone(pytz.UTC)
        sunrise = dt_util.as_local(
            get_astral_event_date(self.hass, "sunrise", dt_util.as_utc(test_time))
        )
        sunset = dt_util.as_local(
            get_astral_event_date(self.hass, "sunset", dt_util.as_utc(test_time))
        )
        config = {
            "binary_sensor": [
                {
                    "platform": "tod",
                    "name": "Day",
                    "after": "sunrise",
                    "before": "sunset",
                }
            ]
        }
        entity_id = "binary_sensor.day"
        testtime = sunrise + timedelta(seconds=-1)
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):
            setup_component(self.hass, "binary_sensor", config)

            self.hass.block_till_done()
            state = self.hass.states.get(entity_id)
            assert state.state == STATE_OFF

        testtime = sunrise
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):

            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_ON

        testtime = sunrise + timedelta(seconds=1)
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):

            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_ON

        self.hass.block_till_done()

        testtime = sunset + timedelta(seconds=-1)
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):

            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_ON

        self.hass.block_till_done()

        testtime = sunset
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):

            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_OFF

        self.hass.block_till_done()

        testtime = sunset + timedelta(seconds=1)
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):

            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_OFF

    def test_from_sunset_to_sunrise(self):
        """Test period from sunset to sunrise."""
        test_time = self.hass.config.time_zone.localize(
            datetime(2019, 1, 12)
        ).astimezone(pytz.UTC)
        sunset = dt_util.as_local(get_astral_event_date(self.hass, "sunset", test_time))
        sunrise = dt_util.as_local(get_astral_event_next(self.hass, "sunrise", sunset))
        # assert sunset == sunrise
        config = {
            "binary_sensor": [
                {
                    "platform": "tod",
                    "name": "Night",
                    "after": "sunset",
                    "before": "sunrise",
                }
            ]
        }
        entity_id = "binary_sensor.night"
        testtime = sunset + timedelta(minutes=-1)
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):
            setup_component(self.hass, "binary_sensor", config)

            self.hass.block_till_done()
            state = self.hass.states.get(entity_id)
            assert state.state == STATE_OFF

        testtime = sunset
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):

            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_ON

        testtime = sunset + timedelta(minutes=1)
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):

            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_ON

        testtime = sunrise + timedelta(minutes=-1)
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):

            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_ON

        testtime = sunrise
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):

            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            self.hass.block_till_done()
            # assert state == "dupa"
            assert state.state == STATE_OFF

        testtime = sunrise + timedelta(minutes=1)
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):

            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_OFF

    def test_offset(self):
        """Test offset."""
        after = self.hass.config.time_zone.localize(
            datetime(2019, 1, 10, 18, 0, 0)
        ).astimezone(pytz.UTC) + timedelta(hours=1, minutes=34)

        before = self.hass.config.time_zone.localize(
            datetime(2019, 1, 10, 22, 0, 0)
        ).astimezone(pytz.UTC) + timedelta(hours=1, minutes=45)

        entity_id = "binary_sensor.evening"
        config = {
            "binary_sensor": [
                {
                    "platform": "tod",
                    "name": "Evening",
                    "after": "18:00",
                    "after_offset": "1:34",
                    "before": "22:00",
                    "before_offset": "1:45",
                }
            ]
        }
        testtime = after + timedelta(seconds=-1)
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):
            setup_component(self.hass, "binary_sensor", config)

        self.hass.block_till_done()
        state = self.hass.states.get(entity_id)
        assert state.state == STATE_OFF

        testtime = after
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):
            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_ON

        testtime = before + timedelta(seconds=-1)
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):
            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_ON

        testtime = before
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):
            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_OFF

        testtime = before + timedelta(seconds=1)
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):
            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_OFF

    def test_offset_overnight(self):
        """Test offset overnight."""
        after = self.hass.config.time_zone.localize(
            datetime(2019, 1, 10, 18, 0, 0)
        ).astimezone(pytz.UTC) + timedelta(hours=1, minutes=34)
        entity_id = "binary_sensor.evening"
        config = {
            "binary_sensor": [
                {
                    "platform": "tod",
                    "name": "Evening",
                    "after": "18:00",
                    "after_offset": "1:34",
                    "before": "22:00",
                    "before_offset": "3:00",
                }
            ]
        }
        testtime = after + timedelta(seconds=-1)
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):
            setup_component(self.hass, "binary_sensor", config)

        self.hass.block_till_done()
        state = self.hass.states.get(entity_id)
        assert state.state == STATE_OFF

        testtime = after
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):
            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_ON

    def test_norwegian_case_winter(self):
        """Test location in Norway where the sun doesn't set in summer."""
        self.hass.config.latitude = 69.6
        self.hass.config.longitude = 18.8

        test_time = self.hass.config.time_zone.localize(
            datetime(2010, 1, 1)
        ).astimezone(pytz.UTC)
        sunrise = dt_util.as_local(
            get_astral_event_next(self.hass, "sunrise", dt_util.as_utc(test_time))
        )
        sunset = dt_util.as_local(
            get_astral_event_next(self.hass, "sunset", dt_util.as_utc(test_time))
        )
        config = {
            "binary_sensor": [
                {
                    "platform": "tod",
                    "name": "Day",
                    "after": "sunrise",
                    "before": "sunset",
                }
            ]
        }
        entity_id = "binary_sensor.day"
        testtime = test_time
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):
            setup_component(self.hass, "binary_sensor", config)

            self.hass.block_till_done()
            state = self.hass.states.get(entity_id)
            assert state.state == STATE_OFF

        testtime = sunrise + timedelta(seconds=-1)
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):

            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_OFF

        testtime = sunrise
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):

            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_ON

        testtime = sunrise + timedelta(seconds=1)
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):

            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_ON

        self.hass.block_till_done()

        testtime = sunset + timedelta(seconds=-1)
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):

            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_ON

        self.hass.block_till_done()

        testtime = sunset
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):

            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_OFF

        self.hass.block_till_done()

        testtime = sunset + timedelta(seconds=1)
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):

            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_OFF

    def test_norwegian_case_summer(self):
        """Test location in Norway where the sun doesn't set in summer."""
        self.hass.config.latitude = 69.6
        self.hass.config.longitude = 18.8

        test_time = self.hass.config.time_zone.localize(
            datetime(2010, 6, 1)
        ).astimezone(pytz.UTC)

        sunrise = dt_util.as_local(
            get_astral_event_next(self.hass, "sunrise", dt_util.as_utc(test_time))
        )
        sunset = dt_util.as_local(
            get_astral_event_next(self.hass, "sunset", dt_util.as_utc(test_time))
        )
        config = {
            "binary_sensor": [
                {
                    "platform": "tod",
                    "name": "Day",
                    "after": "sunrise",
                    "before": "sunset",
                }
            ]
        }
        entity_id = "binary_sensor.day"
        testtime = test_time
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):
            setup_component(self.hass, "binary_sensor", config)

            self.hass.block_till_done()
            state = self.hass.states.get(entity_id)
            assert state.state == STATE_OFF

        testtime = sunrise + timedelta(seconds=-1)
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):

            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_OFF

        testtime = sunrise
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):

            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_ON

        testtime = sunrise + timedelta(seconds=1)
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):

            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_ON

        self.hass.block_till_done()

        testtime = sunset + timedelta(seconds=-1)
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):

            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_ON

        self.hass.block_till_done()

        testtime = sunset
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):

            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_OFF

        self.hass.block_till_done()

        testtime = sunset + timedelta(seconds=1)
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):

            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_OFF

    def test_sun_offset(self):
        """Test sun event with offset."""
        test_time = self.hass.config.time_zone.localize(
            datetime(2019, 1, 12)
        ).astimezone(pytz.UTC)
        sunrise = dt_util.as_local(
            get_astral_event_date(self.hass, "sunrise", dt_util.as_utc(test_time))
            + timedelta(hours=-1, minutes=-30)
        )
        sunset = dt_util.as_local(
            get_astral_event_date(self.hass, "sunset", dt_util.as_utc(test_time))
            + timedelta(hours=1, minutes=30)
        )
        config = {
            "binary_sensor": [
                {
                    "platform": "tod",
                    "name": "Day",
                    "after": "sunrise",
                    "after_offset": "-1:30",
                    "before": "sunset",
                    "before_offset": "1:30",
                }
            ]
        }
        entity_id = "binary_sensor.day"
        testtime = sunrise + timedelta(seconds=-1)
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):
            setup_component(self.hass, "binary_sensor", config)

            self.hass.block_till_done()
            state = self.hass.states.get(entity_id)
            assert state.state == STATE_OFF

        testtime = sunrise
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):

            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_ON

        testtime = sunrise + timedelta(seconds=1)
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):

            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_ON

        self.hass.block_till_done()

        testtime = sunset + timedelta(seconds=-1)
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):

            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_ON

        self.hass.block_till_done()

        testtime = sunset
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):

            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_OFF

        self.hass.block_till_done()

        testtime = sunset + timedelta(seconds=1)
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):

            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_OFF

        test_time = test_time + timedelta(days=1)
        sunrise = dt_util.as_local(
            get_astral_event_date(self.hass, "sunrise", dt_util.as_utc(test_time))
            + timedelta(hours=-1, minutes=-30)
        )
        testtime = sunrise
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):

            self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
            self.hass.block_till_done()

            state = self.hass.states.get(entity_id)
            assert state.state == STATE_ON

    def test_dst(self):
        """Test sun event with offset."""
        self.hass.config.time_zone = pytz.timezone("CET")
        test_time = self.hass.config.time_zone.localize(
            datetime(2019, 3, 30, 3, 0, 0)
        ).astimezone(pytz.UTC)
        config = {
            "binary_sensor": [
                {"platform": "tod", "name": "Day", "after": "2:30", "before": "2:40"}
            ]
        }
        # after 2019-03-30 03:00 CET the next update should ge scheduled
        # at 3:30 not 2:30 local time
        # Internally the
        entity_id = "binary_sensor.day"
        testtime = test_time
        with patch(
            "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
            return_value=testtime,
        ):
            setup_component(self.hass, "binary_sensor", config)

            self.hass.block_till_done()
            state = self.hass.states.get(entity_id)
            state.attributes["after"] == "2019-03-31T03:30:00+02:00"
            state.attributes["before"] == "2019-03-31T03:40:00+02:00"
            state.attributes["next_update"] == "2019-03-31T03:30:00+02:00"
            assert state.state == STATE_OFF
