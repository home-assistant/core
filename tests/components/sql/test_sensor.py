"""The test for the sql sensor platform."""

import pytest
import voluptuous as vol

from homeassistant.components.sql.const import DOMAIN
from homeassistant.components.sql.sensor import validate_sql_select
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_query(hass: HomeAssistant) -> None:
    """Test the SQL sensor."""
    config = {
        "db_url": "sqlite://",
        "query": "SELECT 5 as value",
        "column": "value",
        "name": "Select value SQL query",
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=config,
        entry_id="1",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.select_value_sql_query")
    assert state.state == "5"
    assert state.attributes["value"] == 5


async def test_query_limit(hass: HomeAssistant) -> None:
    """Test the SQL sensor with a query containing 'LIMIT' in lowercase."""
    config = {
        "db_url": "sqlite://",
        "query": "SELECT 5 as value limit 1",
        "column": "value",
        "name": "Select value SQL query",
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=config,
        entry_id="1",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.select_value_sql_query")
    assert state.state == "5"
    assert state.attributes["value"] == 5


async def test_invalid_query(hass: HomeAssistant) -> None:
    """Test the SQL sensor for invalid queries."""
    with pytest.raises(vol.Invalid):
        validate_sql_select("DROP TABLE *")
    config = {
        "db_url": "sqlite://",
        "query": "SELECT * value FROM sqlite_master;",
        "column": "value",
        "name": "Select value SQL query",
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=config,
        entry_id="1",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.select_value_sql_query")
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "url,expected_patterns,not_expected_patterns",
    [
        (
            "sqlite://homeassistant:hunter2@homeassistant.local",
            ["sqlite://****:****@homeassistant.local"],
            ["sqlite://homeassistant:hunter2@homeassistant.local"],
        ),
        (
            "sqlite://homeassistant.local",
            ["sqlite://homeassistant.local"],
            [],
        ),
    ],
)
async def test_invalid_url(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    url: str,
    expected_patterns: list,
    not_expected_patterns: list,
) -> None:
    """Test credentials in url is not logged."""
    config = {
        "sensor": {
            "platform": "sql",
            "db_url": url,
            "queries": [
                {
                    "name": "count_tables",
                    "query": "SELECT 5 as value",
                    "column": "value",
                }
            ],
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    for pattern in not_expected_patterns:
        assert pattern not in caplog.text
    for pattern in expected_patterns:
        assert pattern in caplog.text
