"""Fixtures for the Birthday tests."""

from typing import Any

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.birthday.const import (
    CONF_DAY,
    CONF_MONTH,
    CONF_PERSON,
    CONF_YEAR,
    DOMAIN,
    SUBENTRY_TYPE_BIRTHDAY,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant


def make_subentry(
    name: str, day: int, month: int, year: int | None = None
) -> ConfigSubentryData:
    """Build a birthday subentry."""
    data: dict[str, Any] = {CONF_PERSON: name, CONF_DAY: day, CONF_MONTH: month}
    if year is not None:
        data[CONF_YEAR] = year
    return ConfigSubentryData(
        data=data,
        subentry_type=SUBENTRY_TYPE_BIRTHDAY,
        title=name,
        unique_id=None,
    )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry with a few birthdays."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Birthdays",
        data={},
        subentries_data=[
            make_subentry("Alice", 15, 6, 1990),
            make_subentry("Bob", 10, 3),
            make_subentry("Leap", 29, 2, 2000),
            make_subentry("Baby", 20, 5, 2025),
        ],
    )


@pytest.fixture
def mock_empty_config_entry() -> MockConfigEntry:
    """Return a config entry without any birthday."""
    return MockConfigEntry(domain=DOMAIN, title="Birthdays", data={})


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the integration with a few birthdays."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
