"""Tests the Home Assistant workday binary sensor."""
from datetime import datetime
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest
import voluptuous as vol

from homeassistant.components.workday import binary_sensor
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import UTC

from . import (
    TEST_CONFIG_DAY_AFTER_TOMORROW,
    TEST_CONFIG_EXAMPLE_1,
    TEST_CONFIG_EXAMPLE_2,
    TEST_CONFIG_INCLUDE_HOLIDAY,
    TEST_CONFIG_INCORRECT_ADD_REMOVE,
    TEST_CONFIG_INCORRECT_PROVINCE,
    TEST_CONFIG_NO_PROVINCE,
    TEST_CONFIG_NO_STATE,
    TEST_CONFIG_REMOVE_HOLIDAY,
    TEST_CONFIG_REMOVE_NAMED,
    TEST_CONFIG_TOMORROW,
    TEST_CONFIG_WITH_PROVINCE,
    TEST_CONFIG_WITH_STATE,
    TEST_CONFIG_YESTERDAY,
    init_integration,
)


async def test_valid_country_yaml() -> None:
    """Test valid country from yaml."""
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


@pytest.mark.parametrize(
    ("config", "expected_state"),
    [
        (TEST_CONFIG_WITH_PROVINCE, "off"),
        (TEST_CONFIG_NO_PROVINCE, "off"),
        (TEST_CONFIG_WITH_STATE, "on"),
        (TEST_CONFIG_NO_STATE, "on"),
        (TEST_CONFIG_EXAMPLE_1, "on"),
        (TEST_CONFIG_EXAMPLE_2, "off"),
        (TEST_CONFIG_TOMORROW, "off"),
        (TEST_CONFIG_DAY_AFTER_TOMORROW, "off"),
        (TEST_CONFIG_YESTERDAY, "on"),
    ],
)
async def test_setup(
    hass: HomeAssistant,
    config: dict[str, Any],
    expected_state: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setup from various configs."""
    freezer.move_to(datetime(2022, 4, 15, 12, tzinfo=UTC))  # Monday
    await init_integration(hass, config)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state.state == expected_state
    assert state.attributes == {
        "friendly_name": "Workday Sensor",
        "workdays": config["workdays"],
        "excludes": config["excludes"],
        "days_offset": config["days_offset"],
    }


async def test_setup_from_import(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setup from various configs."""
    freezer.move_to(datetime(2022, 4, 15, 12, tzinfo=UTC))  # Monday
    await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "workday",
                "country": "DE",
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state.state == "off"
    assert state.attributes == {
        "friendly_name": "Workday Sensor",
        "workdays": ["mon", "tue", "wed", "thu", "fri"],
        "excludes": ["sat", "sun", "holiday"],
        "days_offset": 0,
    }


async def test_setup_with_invalid_province_from_yaml(hass: HomeAssistant) -> None:
    """Test setup invalid province with import."""

    await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "workday",
                "country": "DE",
                "province": "invalid",
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state is None


async def test_setup_with_working_holiday(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setup from various configs."""
    freezer.move_to(datetime(2017, 1, 6, 12, tzinfo=UTC))  # Friday
    await init_integration(hass, TEST_CONFIG_INCLUDE_HOLIDAY)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state.state == "on"


async def test_setup_add_holiday(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setup from various configs."""
    freezer.move_to(datetime(2020, 2, 24, 12, tzinfo=UTC))  # Monday
    await init_integration(hass, TEST_CONFIG_EXAMPLE_2)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state.state == "off"


async def test_setup_remove_holiday(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setup from various configs."""
    freezer.move_to(datetime(2020, 12, 25, 12, tzinfo=UTC))  # Friday
    await init_integration(hass, TEST_CONFIG_REMOVE_HOLIDAY)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state.state == "on"


async def test_setup_remove_holiday_named(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setup from various configs."""
    freezer.move_to(datetime(2020, 12, 25, 12, tzinfo=UTC))  # Friday
    await init_integration(hass, TEST_CONFIG_REMOVE_NAMED)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state.state == "on"


async def test_setup_day_after_tomorrow(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setup from various configs."""
    freezer.move_to(datetime(2022, 5, 27, 12, tzinfo=UTC))  # Friday
    await init_integration(hass, TEST_CONFIG_DAY_AFTER_TOMORROW)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state.state == "off"


async def test_setup_faulty_province(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup with faulty province."""
    freezer.move_to(datetime(2017, 1, 6, 12, tzinfo=UTC))  # Friday
    await init_integration(hass, TEST_CONFIG_INCORRECT_PROVINCE)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state is None

    assert "There is no subdivision" in caplog.text


async def test_setup_incorrect_add_remove(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup with incorrect add/remove custom holiday."""
    freezer.move_to(datetime(2017, 1, 6, 12, tzinfo=UTC))  # Friday
    await init_integration(hass, TEST_CONFIG_INCORRECT_ADD_REMOVE)

    hass.states.get("binary_sensor.workday_sensor")

    assert (
        "Could not add custom holidays: Cannot parse date from string '2023-12-32'"
        in caplog.text
    )
    assert "No holiday found matching '2023-12-32'" in caplog.text
