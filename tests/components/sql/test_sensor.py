"""The test for the sql sensor platform."""
import os

import pytest
import voluptuous as vol

from homeassistant.components.sql.sensor import validate_sql_select
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import get_test_config_dir


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
        "sensor": {
            "platform": "sql",
            "db_url": "sqlite://",
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

    state = hass.states.get("sensor.count_tables")
    assert state.state == "5"
    assert state.attributes["value"] == 5


async def test_query_no_db(hass: HomeAssistant) -> None:
    """Test the SQL sensor."""
    config = {
        "sensor": {
            "platform": "sql",
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

    state = hass.states.get("sensor.count_tables")
    assert state.state == "5"


async def test_query_value_template(hass: HomeAssistant) -> None:
    """Test the SQL sensor."""
    config = {
        "sensor": {
            "platform": "sql",
            "db_url": "sqlite://",
            "queries": [
                {
                    "name": "count_tables",
                    "query": "SELECT 5.01 as value",
                    "column": "value",
                    "value_template": "{{ value | int }}",
                }
            ],
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.count_tables")
    assert state.state == "5"


async def test_query_limit(hass: HomeAssistant) -> None:
    """Test the SQL sensor with a query containing 'LIMIT' in lowercase."""
    config = {
        "sensor": {
            "platform": "sql",
            "db_url": "sqlite://",
            "queries": [
                {
                    "name": "count_tables",
                    "query": "SELECT 5 as value limit 1",
                    "column": "value",
                }
            ],
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.count_tables")
    assert state.state == "5"
    assert state.attributes["value"] == 5


async def test_query_no_value(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the SQL sensor with a query that returns no value."""
    config = {
        "sensor": {
            "platform": "sql",
            "db_url": "sqlite://",
            "queries": [
                {
                    "name": "count_tables",
                    "query": "SELECT 5 as value where 1=2",
                    "column": "value",
                }
            ],
        }
    }

    assert await async_setup_component(hass, "sensor", config)
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
        "sensor": {
            "platform": "sql",
            "db_url": "sqlite://",
            "queries": [
                {
                    "name": "count_tables",
                    "query": "SELECT * value FROM sqlite_master;",
                    "column": "value",
                }
            ],
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.count_tables")
    assert state.state == STATE_UNKNOWN


async def test_value_float_and_date(hass: HomeAssistant) -> None:
    """Test the SQL sensor with a query has float as value."""
    config = {
        "sensor": {
            "platform": "sql",
            "db_url": "sqlite://",
            "queries": [
                {
                    "name": "float_value",
                    "query": "SELECT 5 as value, cast(5.01 as decimal(10,2)) as value2",
                    "column": "value",
                },
            ],
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.float_value")
    assert state.state == "5"
    assert isinstance(state.attributes["value2"], float)


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
