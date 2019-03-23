"""The tests for the Sun component."""
# pylint: disable=protected-access
import unittest
from unittest.mock import patch
from datetime import timedelta, datetime

from homeassistant.setup import setup_component
import homeassistant.core as ha
import homeassistant.util.dt as dt_util
import homeassistant.components.sun as sun

from tests.common import get_test_home_assistant


# pylint: disable=invalid-name
class TestSun(unittest.TestCase):
    """Test the sun module."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setting_rising(self):
        """Test retrieving sun setting and rising."""
        utc_now = datetime(2016, 11, 1, 8, 0, 0, tzinfo=dt_util.UTC)
        with patch('homeassistant.helpers.condition.dt_util.utcnow',
                   return_value=utc_now):
            setup_component(self.hass, sun.DOMAIN, {
                sun.DOMAIN: {sun.CONF_ELEVATION: 0}})

        self.hass.block_till_done()
        state = self.hass.states.get(sun.ENTITY_ID)

        from astral import Astral

        astral = Astral()
        utc_today = utc_now.date()

        latitude = self.hass.config.latitude
        longitude = self.hass.config.longitude

        mod = -1
        while True:
            next_dawn = (astral.dawn_utc(
                utc_today + timedelta(days=mod), latitude, longitude))
            if next_dawn > utc_now:
                break
            mod += 1

        mod = -1
        while True:
            next_dusk = (astral.dusk_utc(
                utc_today + timedelta(days=mod), latitude, longitude))
            if next_dusk > utc_now:
                break
            mod += 1

        mod = -1
        while True:
            next_midnight = (astral.solar_midnight_utc(
                utc_today + timedelta(days=mod), longitude))
            if next_midnight > utc_now:
                break
            mod += 1

        mod = -1
        while True:
            next_noon = (astral.solar_noon_utc(
                utc_today + timedelta(days=mod), longitude))
            if next_noon > utc_now:
                break
            mod += 1

        mod = -1
        while True:
            next_rising = (astral.sunrise_utc(
                utc_today + timedelta(days=mod), latitude, longitude))
            if next_rising > utc_now:
                break
            mod += 1

        mod = -1
        while True:
            next_setting = (astral.sunset_utc(
                utc_today + timedelta(days=mod), latitude, longitude))
            if next_setting > utc_now:
                break
            mod += 1

        assert next_dawn == dt_util.parse_datetime(
            state.attributes[sun.STATE_ATTR_NEXT_DAWN])
        assert next_dusk == dt_util.parse_datetime(
            state.attributes[sun.STATE_ATTR_NEXT_DUSK])
        assert next_midnight == dt_util.parse_datetime(
            state.attributes[sun.STATE_ATTR_NEXT_MIDNIGHT])
        assert next_noon == dt_util.parse_datetime(
            state.attributes[sun.STATE_ATTR_NEXT_NOON])
        assert next_rising == dt_util.parse_datetime(
            state.attributes[sun.STATE_ATTR_NEXT_RISING])
        assert next_setting == dt_util.parse_datetime(
            state.attributes[sun.STATE_ATTR_NEXT_SETTING])

    def test_state_change(self):
        """Test if the state changes at next setting/rising."""
        now = datetime(2016, 6, 1, 8, 0, 0, tzinfo=dt_util.UTC)
        with patch('homeassistant.helpers.condition.dt_util.utcnow',
                   return_value=now):
            setup_component(self.hass, sun.DOMAIN, {
                sun.DOMAIN: {sun.CONF_ELEVATION: 0}})

        self.hass.block_till_done()

        test_time = dt_util.parse_datetime(
            self.hass.states.get(sun.ENTITY_ID)
            .attributes[sun.STATE_ATTR_NEXT_RISING])
        assert test_time is not None

        assert sun.STATE_BELOW_HORIZON == \
            self.hass.states.get(sun.ENTITY_ID).state

        self.hass.bus.fire(ha.EVENT_TIME_CHANGED,
                           {ha.ATTR_NOW: test_time + timedelta(seconds=5)})

        self.hass.block_till_done()

        assert sun.STATE_ABOVE_HORIZON == \
            self.hass.states.get(sun.ENTITY_ID).state

    def test_norway_in_june(self):
        """Test location in Norway where the sun doesn't set in summer."""
        self.hass.config.latitude = 69.6
        self.hass.config.longitude = 18.8

        june = datetime(2016, 6, 1, tzinfo=dt_util.UTC)

        with patch('homeassistant.helpers.condition.dt_util.utcnow',
                   return_value=june):
            assert setup_component(self.hass, sun.DOMAIN, {
                sun.DOMAIN: {sun.CONF_ELEVATION: 0}})

        state = self.hass.states.get(sun.ENTITY_ID)
        assert state is not None

        assert dt_util.parse_datetime(
            state.attributes[sun.STATE_ATTR_NEXT_RISING]) == \
            datetime(2016, 7, 25, 23, 23, 39, tzinfo=dt_util.UTC)
        assert dt_util.parse_datetime(
            state.attributes[sun.STATE_ATTR_NEXT_SETTING]) == \
            datetime(2016, 7, 26, 22, 19, 1, tzinfo=dt_util.UTC)
