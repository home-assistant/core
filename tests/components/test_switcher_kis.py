"""Test case for the switcher_kis component."""

# pylint: disable=invalid-sequence-index,broad-except
from random import choice, randint, sample
from string import ascii_lowercase, digits
from traceback import format_exc
from typing import Dict, List, Tuple
from unittest import TestCase
from unittest.mock import patch

from aioswitcher.consts import DAYS_INT_DICT, WEEKDAY_TUP
from aioswitcher.schedules import calc_next_run_for_schedule
from aioswitcher.tools import (create_weekdays_value,
                               timedelta_str_to_schedule_time)
from homeassistant.components.switcher_kis import (
    CONF_DEVICE_ID, CONF_DEVICE_PASSWORD, CONF_INCLUDE_SCHEDULE_SENSORS,
    CONF_PHONE_ID, CONF_SCHEDULE_SCAN_INTERVAL, DOMAIN)
from homeassistant.const import CONF_FRIENDLY_NAME, CONF_ICON, CONF_NAME
from homeassistant.setup import setup_component
from tests.common import assert_setup_component, get_test_home_assistant


def create_configuration() -> Tuple[Dict, Dict]:
    """Use to create a dummy configuration."""
    dummy_phone_id = str(randint(1000, 9999))
    dummy_device_id = ''.join(
        choice(ascii_lowercase + digits) for _ in range(6))
    dummy_device_password = str(randint(10000000, 99999999))
    dummy_minutes_interval = randint(5, 50)

    minimal_config = {
        DOMAIN: {
            CONF_PHONE_ID: dummy_phone_id,
            CONF_DEVICE_ID: dummy_device_id,
            CONF_DEVICE_PASSWORD: dummy_device_password
        }}

    full_config = {
        DOMAIN: {
            CONF_PHONE_ID: dummy_phone_id,
            CONF_DEVICE_ID: dummy_device_id,
            CONF_DEVICE_PASSWORD: dummy_device_password,
            CONF_INCLUDE_SCHEDULE_SENSORS: True,
            CONF_SCHEDULE_SCAN_INTERVAL: {
                'minutes': dummy_minutes_interval
            },
            CONF_NAME: 'boiler',
            CONF_FRIENDLY_NAME: "my boiler",
            CONF_ICON: 'mdi:dummy-icon'
        }}

    return minimal_config, full_config


def create_random_time() -> str:
    """Use to create a random HH:MM time."""
    hour = '00{}'.format(str(randint(0, 23)))[-2:]
    minute = '00{}'.format(str(randint(0, 59)))[-2:]

    return hour + ':' + minute


def create_random_weekdays_list() -> List[int]:
    """Use to create a random list of int represnations of the weekdays."""
    days_list = [0]
    rand_days = sample(WEEKDAY_TUP, randint(0, 7))

    for day in rand_days:
        days_list.append(DAYS_INT_DICT[day])

    return days_list


def create_rand_recur_days_list() -> List[str]:
    """Use to create a random list of str represnations of the weekdays."""
    return sample(WEEKDAY_TUP, randint(1, 7))


class TestSwitcherKisComponent(TestCase):
    """Test the switcher_kis component."""

    patcher = minimal_config = full_config = None

    @classmethod
    def setUpClass(cls) -> None:
        """Set up things to be run before setup are started."""
        cls.patcher = patch(
            'aioswitcher.bridge.SwitcherV2Thread.start')
        cls.patcher.start()
        cls.minimal_config, cls.full_config = create_configuration()

    @classmethod
    def tearDownClass(cls) -> None:
        """Tear down things to be run after all is done."""
        if cls.patcher:
            cls.patcher.stop()

    def setUp(self) -> None:
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self) -> None:
        """Stop everything that was started."""
        self.hass.stop()

    def test_minimal_config(self) -> None:
        """Test setup with configuration minimal entries."""
        with assert_setup_component(6):
            assert setup_component(
                self.hass, DOMAIN, TestSwitcherKisComponent.minimal_config)

    def test_full_config(self) -> None:
        """Test setup with configuration maximum entries."""
        with assert_setup_component(8):
            assert setup_component(
                self.hass, DOMAIN, TestSwitcherKisComponent.full_config)

    def test_convert_timedelta_schedule(self) -> None:
        """Test the timedelta_str_to_schedule_time tool."""
        try:
            result = timedelta_str_to_schedule_time(create_random_time())
            self.assertTrue(isinstance(result, str))
        except Exception:
            self.fail(format_exc())

    def test_converter_create_week_days(self) -> None:
        """Test the create_weekdays_value tool."""
        try:
            result = create_weekdays_value(create_random_weekdays_list())
            self.assertTrue(isinstance(result, str))
        except Exception:
            self.fail(format_exc())

    def test_schedule_next_runtime_calc(self) -> None:
        """Test the calc_next_run_for_schedule tool."""
        recurring_patch = non_recurring_patch = None
        try:
            recurring_patch = patch(
                'aioswitcher.schedules.SwitcherV2Schedule',
                recurring=True,
                start_time=create_random_time(),
                days=create_rand_recur_days_list())

            non_recurring_patch = patch(
                'aioswitcher.schedules.SwitcherV2Schedule',
                recurring=False,
                start_time=create_random_time())

            recurring_schedule = recurring_patch.start()
            recurring_result = calc_next_run_for_schedule(recurring_schedule)
            self.assertTrue(isinstance(recurring_result, str))

            non_recurring_schedule = non_recurring_patch.start()
            non_recurring_result = calc_next_run_for_schedule(
                non_recurring_schedule)
            self.assertTrue(isinstance(non_recurring_result, str))

        except Exception:
            self.fail(format_exc())
        finally:
            if recurring_patch:
                recurring_patch.stop()
            if non_recurring_patch:
                non_recurring_patch.stop()
