"""Tests the Home Assistant workday binary sensor."""

from __future__ import annotations

from typing import Any

from homeassistant.components.workday.const import (
    DEFAULT_EXCLUDES,
    DEFAULT_NAME,
    DEFAULT_OFFSET,
    DEFAULT_WORKDAYS,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def init_integration(
    hass: HomeAssistant,
    config: dict[str, Any],
    entry_id: str = "1",
    source: str = SOURCE_USER,
) -> MockConfigEntry:
    """Set up the Scrape integration in Home Assistant."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=source,
        data={},
        options=config,
        entry_id=entry_id,
    )

    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


TEST_CONFIG_NO_COUNTRY = {
    "name": DEFAULT_NAME,
    "excludes": DEFAULT_EXCLUDES,
    "days_offset": DEFAULT_OFFSET,
    "workdays": DEFAULT_WORKDAYS,
    "add_holidays": [],
    "remove_holidays": [],
}
TEST_CONFIG_NO_COUNTRY_ADD_HOLIDAY = {
    "name": DEFAULT_NAME,
    "excludes": DEFAULT_EXCLUDES,
    "days_offset": DEFAULT_OFFSET,
    "workdays": DEFAULT_WORKDAYS,
    "add_holidays": ["2020-02-24"],
    "remove_holidays": [],
}
TEST_CONFIG_WITH_PROVINCE = {
    "name": DEFAULT_NAME,
    "country": "DE",
    "province": "BW",
    "excludes": DEFAULT_EXCLUDES,
    "days_offset": DEFAULT_OFFSET,
    "workdays": DEFAULT_WORKDAYS,
    "add_holidays": [],
    "remove_holidays": [],
    "language": "de",
}
TEST_CONFIG_NO_LANGUAGE_CONFIGURED = {
    "name": DEFAULT_NAME,
    "country": "DE",
    "province": "BW",
    "excludes": DEFAULT_EXCLUDES,
    "days_offset": DEFAULT_OFFSET,
    "workdays": DEFAULT_WORKDAYS,
    "add_holidays": [],
    "remove_holidays": [],
}
TEST_CONFIG_INCORRECT_COUNTRY = {
    "name": DEFAULT_NAME,
    "country": "ZZ",
    "excludes": DEFAULT_EXCLUDES,
    "days_offset": DEFAULT_OFFSET,
    "workdays": DEFAULT_WORKDAYS,
    "add_holidays": [],
    "remove_holidays": [],
    "language": "de",
}
TEST_CONFIG_INCORRECT_PROVINCE = {
    "name": DEFAULT_NAME,
    "country": "DE",
    "province": "ZZ",
    "excludes": DEFAULT_EXCLUDES,
    "days_offset": DEFAULT_OFFSET,
    "workdays": DEFAULT_WORKDAYS,
    "add_holidays": [],
    "remove_holidays": [],
    "language": "de",
}
TEST_CONFIG_NO_PROVINCE = {
    "name": DEFAULT_NAME,
    "country": "DE",
    "excludes": DEFAULT_EXCLUDES,
    "days_offset": DEFAULT_OFFSET,
    "workdays": DEFAULT_WORKDAYS,
    "add_holidays": [],
    "remove_holidays": [],
    "language": "de",
}
TEST_CONFIG_WITH_STATE = {
    "name": DEFAULT_NAME,
    "country": "US",
    "province": "CA",
    "excludes": DEFAULT_EXCLUDES,
    "days_offset": DEFAULT_OFFSET,
    "workdays": DEFAULT_WORKDAYS,
    "add_holidays": [],
    "remove_holidays": [],
    "language": "en_US",
}
TEST_CONFIG_NO_STATE = {
    "name": DEFAULT_NAME,
    "country": "US",
    "excludes": DEFAULT_EXCLUDES,
    "days_offset": DEFAULT_OFFSET,
    "workdays": DEFAULT_WORKDAYS,
    "add_holidays": [],
    "remove_holidays": [],
    "language": "en_US",
}
TEST_CONFIG_INCLUDE_HOLIDAY = {
    "name": DEFAULT_NAME,
    "country": "DE",
    "province": "BW",
    "excludes": ["sat", "sun"],
    "days_offset": DEFAULT_OFFSET,
    "workdays": ["holiday"],
    "add_holidays": [],
    "remove_holidays": [],
    "language": "de",
}
TEST_CONFIG_EXAMPLE_1 = {
    "name": DEFAULT_NAME,
    "country": "US",
    "excludes": ["sat", "sun"],
    "days_offset": DEFAULT_OFFSET,
    "workdays": DEFAULT_WORKDAYS,
    "add_holidays": [],
    "remove_holidays": [],
    "language": "en_US",
}
TEST_CONFIG_EXAMPLE_2 = {
    "name": DEFAULT_NAME,
    "country": "DE",
    "province": "BW",
    "excludes": DEFAULT_EXCLUDES,
    "days_offset": DEFAULT_OFFSET,
    "workdays": ["mon", "wed", "fri"],
    "add_holidays": ["2020-02-24"],
    "remove_holidays": [],
    "language": "de",
}
TEST_CONFIG_REMOVE_HOLIDAY = {
    "name": DEFAULT_NAME,
    "country": "US",
    "excludes": DEFAULT_EXCLUDES,
    "days_offset": DEFAULT_OFFSET,
    "workdays": DEFAULT_WORKDAYS,
    "add_holidays": [],
    "remove_holidays": ["2020-12-25", "2020-11-26"],
    "language": "en_US",
}
TEST_CONFIG_REMOVE_NAMED = {
    "name": DEFAULT_NAME,
    "country": "US",
    "excludes": DEFAULT_EXCLUDES,
    "days_offset": DEFAULT_OFFSET,
    "workdays": DEFAULT_WORKDAYS,
    "add_holidays": [],
    "remove_holidays": ["Not a Holiday", "Christmas", "Thanksgiving"],
    "language": "en_US",
}
TEST_CONFIG_REMOVE_DATE = {
    "name": DEFAULT_NAME,
    "country": "US",
    "excludes": DEFAULT_EXCLUDES,
    "days_offset": DEFAULT_OFFSET,
    "workdays": DEFAULT_WORKDAYS,
    "add_holidays": [],
    "remove_holidays": ["2024-02-05", "2024-02-06"],
    "language": "en_US",
}
TEST_CONFIG_TOMORROW = {
    "name": DEFAULT_NAME,
    "country": "DE",
    "excludes": DEFAULT_EXCLUDES,
    "days_offset": 1,
    "workdays": DEFAULT_WORKDAYS,
    "add_holidays": [],
    "remove_holidays": [],
    "language": "de",
}
TEST_CONFIG_DAY_AFTER_TOMORROW = {
    "name": DEFAULT_NAME,
    "country": "DE",
    "excludes": DEFAULT_EXCLUDES,
    "days_offset": 2,
    "workdays": DEFAULT_WORKDAYS,
    "add_holidays": [],
    "remove_holidays": [],
    "language": "de",
}
TEST_CONFIG_YESTERDAY = {
    "name": DEFAULT_NAME,
    "country": "DE",
    "excludes": DEFAULT_EXCLUDES,
    "days_offset": -1,
    "workdays": DEFAULT_WORKDAYS,
    "add_holidays": [],
    "remove_holidays": [],
    "language": "de",
}
TEST_CONFIG_INCORRECT_ADD_REMOVE = {
    "name": DEFAULT_NAME,
    "country": "DE",
    "province": "BW",
    "excludes": DEFAULT_EXCLUDES,
    "days_offset": DEFAULT_OFFSET,
    "workdays": DEFAULT_WORKDAYS,
    "add_holidays": ["2023-12-32"],
    "remove_holidays": ["2023-12-32"],
    "language": "de",
}
TEST_CONFIG_INCORRECT_ADD_DATE_RANGE = {
    "name": DEFAULT_NAME,
    "country": "DE",
    "province": "BW",
    "excludes": DEFAULT_EXCLUDES,
    "days_offset": DEFAULT_OFFSET,
    "workdays": DEFAULT_WORKDAYS,
    "add_holidays": ["2023-12-01", "2023-12-30,2023-12-32"],
    "remove_holidays": [],
    "language": "de",
}
TEST_CONFIG_INCORRECT_REMOVE_DATE_RANGE = {
    "name": DEFAULT_NAME,
    "country": "DE",
    "province": "BW",
    "excludes": DEFAULT_EXCLUDES,
    "days_offset": DEFAULT_OFFSET,
    "workdays": DEFAULT_WORKDAYS,
    "add_holidays": [],
    "remove_holidays": ["2023-12-25", "2023-12-30,2023-12-32"],
    "language": "de",
}
TEST_CONFIG_INCORRECT_ADD_DATE_RANGE_LEN = {
    "name": DEFAULT_NAME,
    "country": "DE",
    "province": "BW",
    "excludes": DEFAULT_EXCLUDES,
    "days_offset": DEFAULT_OFFSET,
    "workdays": DEFAULT_WORKDAYS,
    "add_holidays": ["2023-12-01", "2023-12-29,2023-12-30,2023-12-31"],
    "remove_holidays": [],
    "language": "de",
}
TEST_CONFIG_INCORRECT_REMOVE_DATE_RANGE_LEN = {
    "name": DEFAULT_NAME,
    "country": "DE",
    "province": "BW",
    "excludes": DEFAULT_EXCLUDES,
    "days_offset": DEFAULT_OFFSET,
    "workdays": DEFAULT_WORKDAYS,
    "add_holidays": [],
    "remove_holidays": ["2023-12-25", "2023-12-29,2023-12-30,2023-12-31"],
    "language": "de",
}
TEST_CONFIG_ADD_REMOVE_DATE_RANGE = {
    "name": DEFAULT_NAME,
    "country": "DE",
    "province": "BW",
    "excludes": DEFAULT_EXCLUDES,
    "days_offset": DEFAULT_OFFSET,
    "workdays": DEFAULT_WORKDAYS,
    "add_holidays": ["2022-12-01", "2022-12-05,2022-12-15"],
    "remove_holidays": ["2022-12-04", "2022-12-24,2022-12-26"],
    "language": "de",
}
TEST_LANGUAGE_CHANGE = {
    "name": DEFAULT_NAME,
    "country": "DE",
    "province": "BW",
    "excludes": DEFAULT_EXCLUDES,
    "days_offset": DEFAULT_OFFSET,
    "workdays": DEFAULT_WORKDAYS,
    "add_holidays": ["2022-12-01", "2022-12-05,2022-12-15"],
    "remove_holidays": ["2022-12-04", "2022-12-24,2022-12-26"],
    "language": "en",
}
TEST_LANGUAGE_NO_CHANGE = {
    "name": DEFAULT_NAME,
    "country": "DE",
    "province": "BW",
    "excludes": DEFAULT_EXCLUDES,
    "days_offset": DEFAULT_OFFSET,
    "workdays": DEFAULT_WORKDAYS,
    "add_holidays": ["2022-12-01", "2022-12-05,2022-12-15"],
    "remove_holidays": ["2022-12-04", "2022-12-24,2022-12-26"],
    "language": "de",
}
