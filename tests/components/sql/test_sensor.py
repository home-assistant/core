"""The test for the sql sensor platform."""
import os
from unittest.mock import patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from homeassistant.components.sql.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, get_test_config_dir


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


async def test_import_query(hass: HomeAssistant) -> None:
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

    assert hass.config_entries.async_entries(DOMAIN)
    data = hass.config_entries.async_entries(DOMAIN)[0].data
    assert data[CONF_NAME] == "Select value SQL query"


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


async def test_query_value_template_invalid(hass: HomeAssistant) -> None:
    """Test the SQL sensor."""
    config = {
        "db_url": "sqlite://",
        "query": "SELECT 5.01 as value",
        "column": "value",
        "name": "count_tables",
        "value_template": "{{ value | dontwork }}",
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
    assert state.state == "5.01"


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
async def test_invalid_url_setup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    url: str,
    expected_patterns: str,
    not_expected_patterns: str,
):
    """Test invalid db url with redacted credentials."""
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

    with patch(
        "homeassistant.components.sql.sensor.sqlalchemy.create_engine",
        side_effect=SQLAlchemyError(url),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    for pattern in not_expected_patterns:
        assert pattern not in caplog.text
    for pattern in expected_patterns:
        assert pattern in caplog.text
