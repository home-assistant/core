"""The test for the sql sensor platform."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from sqlalchemy import text as sql_text
from sqlalchemy.exc import SQLAlchemyError

from homeassistant.components.recorder import Recorder
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.sql.const import CONF_QUERY, DOMAIN
from homeassistant.components.sql.sensor import _generate_lambda_stmt
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_ICON,
    CONF_UNIQUE_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfInformation,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import (
    YAML_CONFIG,
    YAML_CONFIG_ALL_TEMPLATES,
    YAML_CONFIG_BINARY,
    YAML_CONFIG_FULL_TABLE_SCAN,
    YAML_CONFIG_FULL_TABLE_SCAN_NO_UNIQUE_ID,
    YAML_CONFIG_FULL_TABLE_SCAN_WITH_MULTIPLE_COLUMNS,
    YAML_CONFIG_WITH_VIEW_THAT_CONTAINS_ENTITY_ID,
    init_integration,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_query_basic(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test the SQL sensor."""
    config = {
        "db_url": "sqlite://",
        "query": "SELECT 5 as value",
        "column": "value",
        "name": "Select value SQL query",
        "unique_id": "very_unique_id",
    }
    await init_integration(hass, config)

    state = hass.states.get("sensor.select_value_sql_query")
    assert state.state == "5"
    assert state.attributes["value"] == 5


async def test_query_cte(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test the SQL sensor with CTE."""
    config = {
        "db_url": "sqlite://",
        "query": "WITH test AS (SELECT 1 AS row_num, 10 AS state) SELECT state FROM test WHERE row_num = 1 LIMIT 1;",
        "column": "state",
        "name": "Select value SQL query CTE",
        "unique_id": "very_unique_id",
    }
    await init_integration(hass, config)

    state = hass.states.get("sensor.select_value_sql_query_cte")
    assert state.state == "10"
    assert state.attributes["state"] == 10


async def test_query_value_template(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test the SQL sensor."""
    config = {
        "db_url": "sqlite://",
        "query": "SELECT 5.01 as value",
        "column": "value",
        "name": "count_tables",
        "value_template": "{{ value | int }}",
    }
    await init_integration(hass, config)

    state = hass.states.get("sensor.count_tables")
    assert state.state == "5"


async def test_query_value_template_invalid(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test the SQL sensor."""
    config = {
        "db_url": "sqlite://",
        "query": "SELECT 5.01 as value",
        "column": "value",
        "name": "count_tables",
        "value_template": "{{ value | dontwork }}",
    }
    await init_integration(hass, config)

    state = hass.states.get("sensor.count_tables")
    assert state.state == "5.01"


async def test_query_limit(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test the SQL sensor with a query containing 'LIMIT' in lowercase."""
    config = {
        "db_url": "sqlite://",
        "query": "SELECT 5 as value limit 1",
        "column": "value",
        "name": "Select value SQL query",
    }
    await init_integration(hass, config)

    state = hass.states.get("sensor.select_value_sql_query")
    assert state.state == "5"
    assert state.attributes["value"] == 5


async def test_query_no_value(
    recorder_mock: Recorder, hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the SQL sensor with a query that returns no value."""
    config = {
        "db_url": "sqlite://",
        "query": "SELECT 5 as value where 1=2",
        "column": "value",
        "name": "count_tables",
    }
    await init_integration(hass, config)

    state = hass.states.get("sensor.count_tables")
    assert state.state == STATE_UNKNOWN

    text = "SELECT 5 as value where 1=2 LIMIT 1; returned no results"
    assert text in caplog.text


async def test_query_mssql_no_result(
    recorder_mock: Recorder, hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the SQL sensor with a query that returns no value."""
    config = {
        "db_url": "mssql://",
        "query": "SELECT 5 as value where 1=2",
        "column": "value",
        "name": "count_tables",
    }
    with (
        patch("homeassistant.components.sql.sensor.sqlalchemy"),
        patch(
            "homeassistant.components.sql.sensor.sqlalchemy.text",
            return_value=sql_text("SELECT TOP 1 5 as value where 1=2"),
        ),
    ):
        await init_integration(hass, config)

    state = hass.states.get("sensor.count_tables")
    assert state.state == STATE_UNKNOWN

    text = "SELECT TOP 1 5 AS VALUE WHERE 1=2 returned no results"
    assert text in caplog.text


@pytest.mark.parametrize(
    ("url", "expected_patterns", "not_expected_patterns"),
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
    recorder_mock: Recorder,
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    url: str,
    expected_patterns: str,
    not_expected_patterns: str,
) -> None:
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
        data={},
        options=config,
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


async def test_invalid_url_on_update(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test invalid db url with redacted credentials on retry."""
    config = {
        "db_url": "sqlite://",
        "query": "SELECT 5 as value",
        "column": "value",
        "name": "count_tables",
    }

    class MockSession:
        """Mock session."""

        def execute(self, query: Any) -> None:
            """Execute the query."""
            raise SQLAlchemyError("sqlite://homeassistant:hunter2@homeassistant.local")

    with patch(
        "homeassistant.components.sql.sensor.scoped_session",
        return_value=MockSession,
    ):
        await init_integration(hass, config)
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(minutes=1),
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    assert "sqlite://****:****@homeassistant.local" in caplog.text


async def test_query_from_yaml(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test the SQL sensor from yaml config."""

    assert await async_setup_component(hass, DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.get_value")
    assert state.state == "5"


async def test_templates_with_yaml(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test the SQL sensor from yaml config with templates."""

    hass.states.async_set("sensor.input1", "on")
    hass.states.async_set("sensor.input2", "on")
    await hass.async_block_till_done()

    assert await async_setup_component(hass, DOMAIN, YAML_CONFIG_ALL_TEMPLATES)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.get_values_with_template")
    assert state.state == "5"
    assert state.attributes[CONF_ICON] == "mdi:on"
    assert state.attributes["entity_picture"] == "/local/picture1.jpg"

    hass.states.async_set("sensor.input1", "off")
    await hass.async_block_till_done()

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(minutes=1),
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.get_values_with_template")
    assert state.state == "5"
    assert state.attributes[CONF_ICON] == "mdi:off"
    assert state.attributes["entity_picture"] == "/local/picture2.jpg"

    hass.states.async_set("sensor.input2", "off")
    await hass.async_block_till_done()

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(minutes=2),
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.get_values_with_template")
    assert state.state == STATE_UNAVAILABLE

    hass.states.async_set("sensor.input1", "on")
    hass.states.async_set("sensor.input2", "on")
    await hass.async_block_till_done()

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(minutes=3),
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.get_values_with_template")
    assert state.state == "5"
    assert state.attributes[CONF_ICON] == "mdi:on"
    assert state.attributes["entity_picture"] == "/local/picture1.jpg"


async def test_config_from_old_yaml(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test the SQL sensor from old yaml config does not create any entity."""
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
    assert not state


@pytest.mark.parametrize(
    ("url", "expected_patterns", "not_expected_patterns"),
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
async def test_invalid_url_setup_from_yaml(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    url: str,
    expected_patterns: str,
    not_expected_patterns: str,
) -> None:
    """Test invalid db url with redacted credentials from yaml setup."""
    config = {
        "sql": {
            "db_url": url,
            "query": "SELECT 5 as value",
            "column": "value",
            "name": "count_tables",
        }
    }

    with patch(
        "homeassistant.components.sql.sensor.sqlalchemy.create_engine",
        side_effect=SQLAlchemyError(url),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    for pattern in not_expected_patterns:
        assert pattern not in caplog.text
    for pattern in expected_patterns:
        assert pattern in caplog.text


async def test_attributes_from_yaml_setup(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test attributes from yaml config."""

    assert await async_setup_component(hass, DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.get_value")

    assert state.state == "5"
    assert state.attributes["device_class"] == SensorDeviceClass.DATA_SIZE
    assert state.attributes["state_class"] == SensorStateClass.MEASUREMENT
    assert state.attributes["unit_of_measurement"] == UnitOfInformation.MEBIBYTES


async def test_binary_data_from_yaml_setup(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test binary data from yaml config."""

    assert await async_setup_component(hass, DOMAIN, YAML_CONFIG_BINARY)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.get_binary_value")
    assert state.state == "0xd34324324230392032"
    assert state.attributes["test_attr"] == "0xd343aa"


async def test_issue_when_using_old_query(
    recorder_mock: Recorder, hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we create an issue for an old query that will do a full table scan."""

    assert await async_setup_component(hass, DOMAIN, YAML_CONFIG_FULL_TABLE_SCAN)
    await hass.async_block_till_done()
    assert "Query contains entity_id but does not reference states_meta" in caplog.text

    assert not hass.states.async_all()
    issue_registry = ir.async_get(hass)

    config = YAML_CONFIG_FULL_TABLE_SCAN["sql"]

    unique_id = config[CONF_UNIQUE_ID]

    issue = issue_registry.async_get_issue(
        DOMAIN, f"entity_id_query_does_full_table_scan_{unique_id}"
    )
    assert issue.translation_placeholders == {"query": config[CONF_QUERY]}


@pytest.mark.parametrize(
    "yaml_config",
    [
        YAML_CONFIG_FULL_TABLE_SCAN_NO_UNIQUE_ID,
        YAML_CONFIG_FULL_TABLE_SCAN_WITH_MULTIPLE_COLUMNS,
    ],
)
async def test_issue_when_using_old_query_without_unique_id(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    yaml_config: dict[str, Any],
) -> None:
    """Test we create an issue for an old query that will do a full table scan."""

    assert await async_setup_component(hass, DOMAIN, yaml_config)
    await hass.async_block_till_done()
    assert "Query contains entity_id but does not reference states_meta" in caplog.text

    assert not hass.states.async_all()
    issue_registry = ir.async_get(hass)

    config = yaml_config["sql"]
    query = config[CONF_QUERY]

    issue = issue_registry.async_get_issue(
        DOMAIN, f"entity_id_query_does_full_table_scan_{query}"
    )
    assert issue.translation_placeholders == {"query": query}


async def test_no_issue_when_view_has_the_text_entity_id_in_it(
    recorder_mock: Recorder, hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we do not trigger the full table scan issue for a custom view."""

    with patch(
        "homeassistant.components.sql.sensor.scoped_session",
    ):
        await init_integration(
            hass, YAML_CONFIG_WITH_VIEW_THAT_CONTAINS_ENTITY_ID["sql"]
        )
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(minutes=1),
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        "Query contains entity_id but does not reference states_meta" not in caplog.text
    )
    assert hass.states.get("sensor.get_entity_id") is not None


async def test_multiple_sensors_using_same_db(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test multiple sensors using the same db."""
    config = {
        "db_url": "sqlite:///",
        "query": "SELECT 5 as value",
        "column": "value",
        "name": "Select value SQL query",
    }
    config2 = {
        "db_url": "sqlite:///",
        "query": "SELECT 5 as value",
        "column": "value",
        "name": "Select value SQL query 2",
    }
    await init_integration(hass, config)
    await init_integration(hass, config2, entry_id="2")

    state = hass.states.get("sensor.select_value_sql_query")
    assert state.state == "5"
    assert state.attributes["value"] == 5

    state = hass.states.get("sensor.select_value_sql_query_2")
    assert state.state == "5"
    assert state.attributes["value"] == 5

    with patch("sqlalchemy.engine.base.Engine.dispose"):
        await hass.async_stop()


async def test_engine_is_disposed_at_stop(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test we dispose of the engine at stop."""
    config = {
        "db_url": "sqlite:///",
        "query": "SELECT 5 as value",
        "column": "value",
        "name": "Select value SQL query",
    }
    await init_integration(hass, config)

    state = hass.states.get("sensor.select_value_sql_query")
    assert state.state == "5"
    assert state.attributes["value"] == 5

    with patch("sqlalchemy.engine.base.Engine.dispose") as mock_engine_dispose:
        await hass.async_stop()

    assert mock_engine_dispose.call_count == 2


async def test_attributes_from_entry_config(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test attributes from entry config."""

    await init_integration(
        hass,
        config={
            "name": "Get Value - With",
            "query": "SELECT 5 as value",
            "column": "value",
            "unit_of_measurement": "MiB",
            "device_class": SensorDeviceClass.DATA_SIZE,
            "state_class": SensorStateClass.TOTAL,
        },
        entry_id="8693d4782ced4fb1ecca4743f29ab8f1",
    )

    state = hass.states.get("sensor.get_value_with")
    assert state.state == "5"
    assert state.attributes["value"] == 5
    assert state.attributes["unit_of_measurement"] == "MiB"
    assert state.attributes["device_class"] == SensorDeviceClass.DATA_SIZE
    assert state.attributes["state_class"] == SensorStateClass.TOTAL

    await init_integration(
        hass,
        config={
            "name": "Get Value - Without",
            "query": "SELECT 5 as value",
            "column": "value",
            "unit_of_measurement": "MiB",
        },
        entry_id="7aec7cd8045fba4778bb0621469e3cd9",
    )

    state = hass.states.get("sensor.get_value_without")
    assert state.state == "5"
    assert state.attributes["value"] == 5
    assert state.attributes["unit_of_measurement"] == "MiB"
    assert "device_class" not in state.attributes
    assert "state_class" not in state.attributes


async def test_query_recover_from_rollback(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the SQL sensor."""
    config = {
        "db_url": "sqlite://",
        "query": "SELECT 5 as value",
        "column": "value",
        "name": "Select value SQL query",
        "unique_id": "very_unique_id",
    }
    await init_integration(hass, config)
    platforms = async_get_platforms(hass, "sql")
    sql_entity = platforms[0].entities["sensor.select_value_sql_query"]

    state = hass.states.get("sensor.select_value_sql_query")
    assert state.state == "5"
    assert state.attributes["value"] == 5

    with patch.object(
        sql_entity,
        "_lambda_stmt",
        _generate_lambda_stmt("Faulty syntax create operational issue"),
    ):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert "sqlite3.OperationalError" in caplog.text

    state = hass.states.get("sensor.select_value_sql_query")
    assert state.state == "5"
    assert state.attributes.get("value") is None

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.select_value_sql_query")
    assert state.state == "5"
    assert state.attributes.get("value") == 5


async def test_setup_without_recorder(hass: HomeAssistant) -> None:
    """Test the SQL sensor without recorder."""

    assert await async_setup_component(hass, DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.get_value")
    assert state.state == "5"
