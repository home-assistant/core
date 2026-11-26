"""Test Workday component setup process."""

from datetime import datetime
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from holidays.utils import country_holidays
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.workday.const import (
    DEFAULT_OFFSET,
    DEFAULT_WORKDAYS,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import UTC

from . import TEST_CONFIG_EXAMPLE_1, TEST_CONFIG_WITH_PROVINCE, init_integration


async def test_load_unload_entry(hass: HomeAssistant) -> None:
    """Test load and unload entry."""
    entry = await init_integration(hass, TEST_CONFIG_EXAMPLE_1)

    state = hass.states.get("binary_sensor.workday_sensor_us")
    assert state

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.workday_sensor_us")
    assert not state


async def test_update_options(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test options update and config entry is reloaded."""
    freezer.move_to(datetime(2023, 4, 12, 12, tzinfo=UTC))  # Monday

    entry = await init_integration(hass, TEST_CONFIG_WITH_PROVINCE)
    assert entry.state is ConfigEntryState.LOADED
    assert entry.update_listeners is not None
    state = hass.states.get("binary_sensor.workday_sensor_de_bw")
    assert state.state == "on"

    new_options = {
        **TEST_CONFIG_WITH_PROVINCE,
        "custom_holidays": {"add_holidays": ["2023-04-12"], "remove_holidays": []},
    }

    hass.config_entries.async_update_entry(entry, options=new_options)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    entry_check = hass.config_entries.async_get_entry("1")
    assert entry_check.state is ConfigEntryState.LOADED
    state = hass.states.get("binary_sensor.workday_sensor_de_bw")
    assert state.state == "off"


async def test_workday_subdiv_aliases() -> None:
    """Test subdiv aliases in holidays library."""

    country = country_holidays(
        country="FR",
        years=2025,
    )
    subdiv_aliases = country.get_subdivision_aliases()
    assert subdiv_aliases["6AE"] == ["Alsace"]


@pytest.mark.parametrize("minor_version", [1, 2])
@pytest.mark.parametrize(
    ("options", "expected_options"),
    [
        pytest.param(
            {
                "country": "DE",
                "excludes": ["sat", "sun"],
                "days_offset": DEFAULT_OFFSET,
                "workdays": DEFAULT_WORKDAYS,
                "add_holidays": ["2023-04-12"],
                "remove_holidays": ["Weihnachtstag"],
                "province": "BW",
                "language": "de",
                "category": ["catholic"],
            },
            {
                "country": "DE",
                "excludes": ["sat", "sun"],
                "days_offset": DEFAULT_OFFSET,
                "workdays": DEFAULT_WORKDAYS,
                "custom_holidays": {
                    "add_holidays": ["2023-04-12"],
                    "remove_holidays": ["Weihnachtstag"],
                },
                "country_settings": {
                    "province": "BW",
                    "language": "de",
                    "category": ["catholic"],
                },
            },
            id="country",
        ),
        pytest.param(
            {
                "excludes": ["sat", "sun"],
                "days_offset": DEFAULT_OFFSET,
                "workdays": DEFAULT_WORKDAYS,
                "add_holidays": [],
                "remove_holidays": [],
            },
            {
                "excludes": ["sat", "sun"],
                "days_offset": DEFAULT_OFFSET,
                "workdays": DEFAULT_WORKDAYS,
                "custom_holidays": {
                    "add_holidays": [],
                    "remove_holidays": [],
                },
            },
            id="no_country",
        ),
    ],
)
async def test_migrate_to_version_2(
    hass: HomeAssistant,
    minor_version: int,
    options: dict[str, Any],
    expected_options: dict[str, Any],
) -> None:
    """Test migration moves the options into sections."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data={},
        options=options,
        entry_id="1",
        title="Test sensor",
        version=1,
        minor_version=minor_version,
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.version == 2
    assert config_entry.minor_version == 2
    assert config_entry.options == expected_options


@pytest.mark.parametrize(
    ("options", "expected_country_settings"),
    [
        pytest.param(
            {"country": "SE", "country_settings": {"language": "sv"}},
            {"language": "sv", "include_sundays": False},
            id="default_added",
        ),
        pytest.param(
            {
                "country": "SE",
                "country_settings": {"language": "sv", "include_sundays": True},
            },
            {"language": "sv", "include_sundays": True},
            id="stored_value_kept",
        ),
        pytest.param(
            {"country": "DE", "country_settings": {"language": "de"}},
            {"language": "de"},
            id="country_without_options",
        ),
    ],
)
async def test_migrate_to_minor_version_2(
    hass: HomeAssistant,
    options: dict[str, Any],
    expected_country_settings: dict[str, Any],
) -> None:
    """Test the migration stores the defaults of the country specific options."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data={},
        options={
            "excludes": ["sat", "sun"],
            "days_offset": DEFAULT_OFFSET,
            "workdays": DEFAULT_WORKDAYS,
            "custom_holidays": {"add_holidays": [], "remove_holidays": []},
            **options,
        },
        entry_id="1",
        title="Test sensor",
        version=2,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.minor_version == 2
    assert config_entry.options["country_settings"] == expected_country_settings
