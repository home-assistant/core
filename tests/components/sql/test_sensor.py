"""The test for the sql sensor platform."""
import os

import pytest
import voluptuous as vol

from homeassistant.components.sql.const import DOMAIN
from homeassistant.components.sql.sensor import validate_sql_select
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from tests.common import get_test_config_dir, MockConfigEntry


@pytest.fixture(autouse=True)
def remove_file():
    """Remove db."""
    yield
    file = os.path.join(get_test_config_dir(), "home-assistant_v2.db")
    if os.path.isfile(file):
        os.remove(file)


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


async def test_query_value_template(hass: HomeAssistant) -> None:
    """Test the SQL sensor."""
    config = {
        "db_url": "sqlite://",
        "query": "SELECT 5.01 as value",
        "column": "value",
        "name": "count_tables",
        "value_template": "{{ value | int }}",
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

    state = hass.states.get("sensor.count_tables")
    assert state.state == "5"


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


async def test_query_no_value(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the SQL sensor with a query that returns no value."""
    config = {
        "db_url": "sqlite://",
        "query": "SELECT 5 as value where 1=2",
        "column": "value",
        "name": "count_tables",
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

    state = hass.states.get("sensor.count_tables")
    assert state.state == STATE_UNKNOWN

    text = "SELECT 5 as value where 1=2 returned no results"
    assert text in caplog.text


async def test_invalid_query(hass: HomeAssistant) -> None:
    """Test the SQL sensor for invalid queries."""
    with pytest.raises(vol.Invalid):
        validate_sql_select("DROP TABLE *")

    config = {
        "db_url": "sqlite://",
        "query": "SELECT * value FROM sqlite_master;",
        "column": "value",
        "name": "count_tables",
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

    state = hass.states.get("sensor.count_tables")
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
    expected_patterns: str,
    not_expected_patterns: str,
):
    """Test credentials in url is not logged."""
    config = {
        "db_url": url,
        "query": "SELECT 5 as value",
        "column": "value",
        "name": "count_tables",
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

    for pattern in not_expected_patterns:
        assert pattern not in caplog.text
    for pattern in expected_patterns:
        assert pattern in caplog.text
