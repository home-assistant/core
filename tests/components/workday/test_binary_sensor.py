"""Tests the Home Assistant workday binary sensor."""
from datetime import date
from unittest.mock import patch

import pytest
import voluptuous as vol

import homeassistant.components.workday.binary_sensor as binary_sensor
from homeassistant.components.workday.const import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import setup_component

from tests.common import (
    MockConfigEntry,
    assert_setup_component,
    get_test_home_assistant,
)
from tests.components.workday import (
    create_workday_test_data,
    create_workday_test_options,
)

FUNCTION_PATH = "homeassistant.components.workday.binary_sensor.get_date"

# WORKDAY_SENSOR = "binary_sensor.workday_sensor"

CONFIG_PROVINCE = create_workday_test_data(country="DE", province="BW")
SENSOR_PROVINCE = "binary_sensor.workday_de_bw"
CONFIG_NOPROVINCE = create_workday_test_data(country="DE")
SENSOR_NOPROVINCE = "binary_sensor.workday_de"

CONFIG_STATE = create_workday_test_data(country="US", state="CA")
SENSOR_STATE = "binary_sensor.workday_us_ca"
CONFIG_NOSTATE = create_workday_test_data(country="US")
SENSOR_NOSTATE = "binary_sensor.workday_us"

CONFIG_INCLUDEHOLIDAY = create_workday_test_data(
    country="DE", province="BW", workdays=["holiday"], excludes=["sat", "sun"]
)
SENSOR_INCLUDEHOLIDAY = "binary_sensor.workday_de_bw"

CONFIG_REMOVE_HOLIDAYS_DATA = create_workday_test_data(
    country="US",
    workdays=["mon", "tue", "wed", "thu", "fri"],
    excludes=["sat", "sun", "holiday"],
)
SENSOR_REMOVE_HOLIDAYS_DATA = "binary_sensor.workday_us"
CONFIG_REMOVE_HOLIDAYS_OPTIONS = create_workday_test_options(
    remove_holidays=["2020-12-25", "2020-11-26"]
)
CONFIG_REMOVE_NAMED_HOLIDAYS_OPTIONS = create_workday_test_options(
    remove_holidays=["Not a Holiday", "Christmas", "Thanksgiving"]
)

CONFIG_TOMORROW = create_workday_test_data(country="DE", days_offset=1)
CONFIG_DAY_AFTER_TOMORROW = create_workday_test_data(country="DE", days_offset=2)
CONFIG_YESTERDAY = create_workday_test_data(country="DE", days_offset=-1)
SENSOR_DE = "binary_sensor.workday_de"

CONFIG_EXAMPLE1 = create_workday_test_data(
    country="US", workdays=["mon", "tue", "wed", "thu", "fri"], excludes=["sat", "sun"]
)
SENSOR_EXAMPLE1 = "binary_sensor.workday_us"
CONFIG_EXAMPLE2_DATA = create_workday_test_data(
    country="DE",
    province="BW",
    workdays=["mon", "wed", "fri"],
    excludes=["sat", "sun", "holiday"],
)
CONFIG_EXAMPLE2_OPTIONS = create_workday_test_options(add_holidays=["2020-02-24"])
SENSOR_EXAMPLE2 = "binary_sensor.workday_de_bw"


async def test_setup_province(hass: HomeAssistant):
    """Set up workday component."""
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data=CONFIG_PROVINCE)
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    entity = hass.states.get(SENSOR_PROVINCE)
    assert entity is not None


async def test_workday_province(hass: HomeAssistant):
    """Test if workdays are reported correctly."""
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data=CONFIG_PROVINCE)
    mock_entry.add_to_hass(hass)
    # Freeze time to a workday - Mar 15th, 2017
    with patch(FUNCTION_PATH, return_value=date(2017, 3, 15)):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    entity = hass.states.get(SENSOR_PROVINCE)
    assert entity.state == STATE_ON


async def test_weekend_province(hass: HomeAssistant):
    """Test if weekends are reported correctly."""
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data=CONFIG_PROVINCE)
    mock_entry.add_to_hass(hass)
    # Freeze time to a weekend - Mar 12th, 2017
    with patch(FUNCTION_PATH, return_value=date(2017, 3, 12)):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    entity = hass.states.get(SENSOR_PROVINCE)
    assert entity.state == STATE_OFF


async def test_public_holiday_province(hass: HomeAssistant):
    """Test if public holidays are reported correctly."""
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data=CONFIG_PROVINCE)
    mock_entry.add_to_hass(hass)
    # Freeze time to a public holiday in province BW - Jan 6th, 2017
    with patch(FUNCTION_PATH, return_value=date(2017, 1, 6)):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    entity = hass.states.get(SENSOR_PROVINCE)
    assert entity.state == STATE_OFF


async def test_setup_component_noprovince(hass: HomeAssistant):
    """Set up workday component."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN, unique_id=DOMAIN, data=CONFIG_NOPROVINCE
    )
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    entity = hass.states.get(SENSOR_NOPROVINCE)
    assert entity is not None


async def test_public_holiday_noprovince(hass: HomeAssistant):
    """Test if workdays are reported correctly."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN, unique_id=DOMAIN, data=CONFIG_NOPROVINCE
    )
    mock_entry.add_to_hass(hass)
    # Freeze time to a public holiday in province BW - Jan 6th, 2017
    with patch(FUNCTION_PATH, return_value=date(2017, 1, 6)):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    entity = hass.states.get(SENSOR_NOPROVINCE)
    assert entity.state == STATE_ON


async def test_public_holiday_state(hass: HomeAssistant):
    """Test if public holidays are reported correctly."""
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data=CONFIG_STATE)
    mock_entry.add_to_hass(hass)
    # Freeze time to a public holiday in state CA - Mar 31st, 2017
    with patch(FUNCTION_PATH, return_value=date(2017, 3, 31)):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    entity = hass.states.get(SENSOR_STATE)
    assert entity.state == STATE_OFF


async def test_public_holiday_nostate(hass: HomeAssistant):
    """Test if public holidays are reported correctly."""
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data=CONFIG_NOSTATE)
    mock_entry.add_to_hass(hass)
    # Freeze time to a public holiday in state CA - Mar 31st, 2017
    with patch(FUNCTION_PATH, return_value=date(2017, 3, 31)):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    entity = hass.states.get(SENSOR_NOSTATE)
    assert entity.state == STATE_ON


async def test_public_holiday_includeholiday(hass: HomeAssistant):
    """Test if public holidays are reported correctly."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN, unique_id=DOMAIN, data=CONFIG_INCLUDEHOLIDAY
    )
    mock_entry.add_to_hass(hass)
    # Freeze time to a public holiday in province BW - Jan 6th, 2017
    with patch(FUNCTION_PATH, return_value=date(2017, 1, 6)):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    entity = hass.states.get(SENSOR_INCLUDEHOLIDAY)
    assert entity.state == STATE_ON


async def test_tomorrow(hass: HomeAssistant):
    """Test if tomorrow are reported correctly."""
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data=CONFIG_TOMORROW)
    mock_entry.add_to_hass(hass)
    # Freeze time to a saturday to test offset - Aug 5th, 2017
    with patch(FUNCTION_PATH, return_value=date(2017, 8, 5)):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    entity = hass.states.get(SENSOR_DE)
    assert entity.state == STATE_OFF


async def test_day_after_tomorrow(hass: HomeAssistant):
    """Test if the day after tomorrow are reported correctly."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN, unique_id=DOMAIN, data=CONFIG_DAY_AFTER_TOMORROW
    )
    mock_entry.add_to_hass(hass)
    # Freeze time to a saturday to test offset - Aug 5th, 2017
    with patch(FUNCTION_PATH, return_value=date(2017, 8, 5)):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    entity = hass.states.get(SENSOR_DE)
    assert entity.state == STATE_ON


async def test_yesterday(hass: HomeAssistant):
    """Test if yesterday are reported correctly."""
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data=CONFIG_YESTERDAY)
    mock_entry.add_to_hass(hass)
    # Freeze time to a saturday to test offset - Aug 5th, 2017
    with patch(FUNCTION_PATH, return_value=date(2017, 8, 5)):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    entity = hass.states.get(SENSOR_DE)
    assert entity.state == STATE_ON


async def test_config_example1_holiday(hass: HomeAssistant):
    """Test if public holidays are reported correctly."""
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data=CONFIG_EXAMPLE1)
    mock_entry.add_to_hass(hass)
    # Freeze time to a Presidents day to test Holiday on a Work day - Jan 20th, 2020
    #   Presidents day Feb 17th 2020 is mon.
    with patch(FUNCTION_PATH, return_value=date(2020, 2, 17)):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    entity = hass.states.get(SENSOR_EXAMPLE1)
    assert entity.state == STATE_ON


async def test_config_example2_tue(hass: HomeAssistant):
    """Test if public holidays are reported correctly."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data=CONFIG_EXAMPLE2_DATA,
        options=CONFIG_EXAMPLE2_OPTIONS,
    )
    mock_entry.add_to_hass(hass)
    # Freeze time to test tue - Feb 18th, 2020
    with patch(FUNCTION_PATH, return_value=date(2020, 2, 18)):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    entity = hass.states.get(SENSOR_EXAMPLE2)
    assert entity.state == STATE_OFF


async def test_config_example2_add_holiday(hass: HomeAssistant):
    """Test if public holidays are reported correctly."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data=CONFIG_EXAMPLE2_DATA,
        options=CONFIG_EXAMPLE2_OPTIONS,
    )
    mock_entry.add_to_hass(hass)
    # Freeze time to test mon, but added as holiday - Feb 24th, 2020
    with patch(FUNCTION_PATH, return_value=date(2020, 2, 24)):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    entity = hass.states.get(SENSOR_EXAMPLE2)
    assert entity.state == STATE_OFF


async def test_config_remove_holidays_xmas(hass: HomeAssistant):
    """Test if removed holidays are reported correctly."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data=CONFIG_REMOVE_HOLIDAYS_DATA,
        options=CONFIG_REMOVE_HOLIDAYS_OPTIONS,
    )
    mock_entry.add_to_hass(hass)
    # Freeze time to test Fri, but remove holiday - December 25, 2020
    with patch(FUNCTION_PATH, return_value=date(2020, 12, 25)):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    entity = hass.states.get(SENSOR_REMOVE_HOLIDAYS_DATA)
    assert entity.state == STATE_ON


async def test_config_remove_named_holidays_xmas(hass: HomeAssistant):
    """Test if removed holidays by name are reported correctly."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data=CONFIG_REMOVE_HOLIDAYS_DATA,
        options=CONFIG_REMOVE_NAMED_HOLIDAYS_OPTIONS,
    )
    mock_entry.add_to_hass(hass)
    # Freeze time to test Fri, but remove holiday - December 25, 2020
    with patch(FUNCTION_PATH, return_value=date(2020, 12, 25)):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    entity = hass.states.get(SENSOR_REMOVE_HOLIDAYS_DATA)
    assert entity.state == STATE_ON


class TestWorkdaySetup:
    """Test class for workday sensor."""

    def setup_method(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        # Set valid default config for test
        self.config_invalidprovince = {
            "binary_sensor": {
                "platform": "workday",
                "country": "DE",
                "province": "invalid",
            }
        }

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_valid_country(self):
        """Test topic name/filter validation."""
        # Invalid UTF-8, must not contain U+D800 to U+DFFF
        with pytest.raises(vol.Invalid):
            binary_sensor.valid_country("\ud800")
        with pytest.raises(vol.Invalid):
            binary_sensor.valid_country("\udfff")
        # Country MUST NOT be empty
        with pytest.raises(vol.Invalid):
            binary_sensor.valid_country("")
        # Country must be supported by holidays
        with pytest.raises(vol.Invalid):
            binary_sensor.valid_country("HomeAssistantLand")

    def test_setup_component_invalidprovince(self):
        """Set up workday component."""
        with assert_setup_component(1, "binary_sensor"):
            setup_component(self.hass, "binary_sensor", self.config_invalidprovince)

        entity = self.hass.states.get("binary_sensor.workday_sensor")
        assert entity is None

    def test_day_to_string(self):
        """Test if day_to_string is behaving correctly."""
        assert binary_sensor.day_to_string(0) == "mon"
        assert binary_sensor.day_to_string(1) == "tue"
        assert binary_sensor.day_to_string(7) == "holiday"
        assert binary_sensor.day_to_string(8) is None
