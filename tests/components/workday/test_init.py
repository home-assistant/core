"""Test Workday component setup process."""

from datetime import datetime

from freezegun.api import FrozenDateTimeFactory
from holidays.utils import country_holidays

from homeassistant.components.workday.const import (
    DEFAULT_OFFSET,
    DEFAULT_WORKDAYS,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import UTC

from . import TEST_CONFIG_EXAMPLE_1, TEST_CONFIG_WITH_PROVINCE, init_integration

from tests.common import MockConfigEntry


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

    new_options = TEST_CONFIG_WITH_PROVINCE.copy()
    new_options["add_holidays"] = ["2023-04-12"]

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


async def test_migrate_minor_version_1_to_2(hass: HomeAssistant) -> None:
    """Test migrates to version 1.2."""
    config = {
        "name": "Test sensor",
        "country": "US",
        "excludes": ["sat", "sun"],
        "days_offset": DEFAULT_OFFSET,
        "workdays": DEFAULT_WORKDAYS,
        "add_holidays": [],
        "remove_holidays": [],
        "language": "en_US",
    }
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data={},
        options=config,
        entry_id="1",
        title="Test sensor",
        minor_version=1,
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_sensor")
    assert state

    assert config_entry.version == 1
    assert config_entry.minor_version == 2
    assert config_entry.options == config
