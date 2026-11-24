"""Tests for the Holiday integration."""

from typing import Any

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.holiday.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

MOCK_CONFIG_DATA = {
    "country": "Germany",
    "province": "BW",
}


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test removing integration."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_DATA)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    state: ConfigEntryState = entry.state
    assert state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("country", "options", "expected_options"),
    [
        pytest.param("SE", {}, {"include_sundays": False}, id="default_added"),
        pytest.param(
            "SE",
            {"include_sundays": True, "categories": ["bank"]},
            {"include_sundays": True, "categories": ["bank"]},
            id="stored_value_kept",
        ),
        pytest.param("AG", {}, {}, id="country_without_options"),
    ],
)
async def test_migrate_entry_to_minor_version_2(
    hass: HomeAssistant,
    country: str,
    options: dict[str, Any],
    expected_options: dict[str, Any],
) -> None:
    """Test the migration stores the defaults of the country specific options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"country": country},
        options=options,
        title="Holiday",
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.minor_version == 2
    assert entry.options == expected_options
