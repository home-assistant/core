"""Test the SQL config flow."""
from __future__ import annotations

from unittest.mock import patch

from sqlalchemy.exc import SQLAlchemyError

from homeassistant import config_entries
from homeassistant.components.recorder import Recorder
from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
from homeassistant.components.sql.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    ENTRY_CONFIG,
    ENTRY_CONFIG_INVALID_COLUMN_NAME,
    ENTRY_CONFIG_INVALID_COLUMN_NAME_OPT,
    ENTRY_CONFIG_INVALID_QUERY,
    ENTRY_CONFIG_INVALID_QUERY_2,
    ENTRY_CONFIG_INVALID_QUERY_2_OPT,
    ENTRY_CONFIG_INVALID_QUERY_3,
    ENTRY_CONFIG_INVALID_QUERY_3_OPT,
    ENTRY_CONFIG_INVALID_QUERY_OPT,
    ENTRY_CONFIG_MULTIPLE_QUERIES,
    ENTRY_CONFIG_MULTIPLE_QUERIES_OPT,
    ENTRY_CONFIG_NO_RESULTS,
    ENTRY_CONFIG_QUERY_NO_READ_ONLY,
    ENTRY_CONFIG_QUERY_NO_READ_ONLY_CTE,
    ENTRY_CONFIG_QUERY_NO_READ_ONLY_CTE_OPT,
    ENTRY_CONFIG_QUERY_NO_READ_ONLY_OPT,
    ENTRY_CONFIG_WITH_VALUE_TEMPLATE,
)

from tests.common import MockConfigEntry


async def test_form(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.sql.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            ENTRY_CONFIG,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Get Value"
    assert result2["options"] == {
        "name": "Get Value",
        "query": "SELECT 5 as value",
        "column": "value",
        "unit_of_measurement": "MiB",
        "device_class": SensorDeviceClass.DATA_SIZE,
        "state_class": SensorStateClass.TOTAL,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_with_value_template(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test for with value template."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.sql.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            ENTRY_CONFIG_WITH_VALUE_TEMPLATE,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Get Value"
    assert result2["options"] == {
        "name": "Get Value",
        "query": "SELECT 5 as value",
        "column": "value",
        "unit_of_measurement": "MiB",
        "value_template": "{{ value }}",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_flow_fails_db_url(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test config flow fails incorrect db url."""
    result4 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result4["type"] == FlowResultType.FORM
    assert result4["step_id"] == config_entries.SOURCE_USER

    with patch(
        "homeassistant.components.sql.config_flow.sqlalchemy.create_engine",
        side_effect=SQLAlchemyError("error_message"),
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result4["flow_id"],
            user_input=ENTRY_CONFIG,
        )

    assert result4["errors"] == {"db_url": "db_url_invalid"}


async def test_flow_fails_invalid_query(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test config flow fails incorrect db url."""
    result4 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result4["type"] == FlowResultType.FORM
    assert result4["step_id"] == config_entries.SOURCE_USER

    result5 = await hass.config_entries.flow.async_configure(
        result4["flow_id"],
        user_input=ENTRY_CONFIG_INVALID_QUERY,
    )

    assert result5["type"] == FlowResultType.FORM
    assert result5["errors"] == {
        "query": "query_invalid",
    }

    result6 = await hass.config_entries.flow.async_configure(
        result4["flow_id"],
        user_input=ENTRY_CONFIG_INVALID_QUERY_2,
    )

    assert result6["type"] == FlowResultType.FORM
    assert result6["errors"] == {
        "query": "query_invalid",
    }

    result6 = await hass.config_entries.flow.async_configure(
        result4["flow_id"],
        user_input=ENTRY_CONFIG_INVALID_QUERY_3,
    )

    assert result6["type"] == FlowResultType.FORM
    assert result6["errors"] == {
        "query": "query_invalid",
    }

    result5 = await hass.config_entries.flow.async_configure(
        result4["flow_id"],
        user_input=ENTRY_CONFIG_QUERY_NO_READ_ONLY,
    )

    assert result5["type"] == FlowResultType.FORM
    assert result5["errors"] == {
        "query": "query_no_read_only",
    }

    result6 = await hass.config_entries.flow.async_configure(
        result4["flow_id"],
        user_input=ENTRY_CONFIG_QUERY_NO_READ_ONLY_CTE,
    )

    assert result6["type"] == FlowResultType.FORM
    assert result6["errors"] == {
        "query": "query_no_read_only",
    }

    result6 = await hass.config_entries.flow.async_configure(
        result4["flow_id"],
        user_input=ENTRY_CONFIG_MULTIPLE_QUERIES,
    )

    assert result6["type"] == FlowResultType.FORM
    assert result6["errors"] == {
        "query": "multiple_queries",
    }

    result5 = await hass.config_entries.flow.async_configure(
        result4["flow_id"],
        user_input=ENTRY_CONFIG_NO_RESULTS,
    )

    assert result5["type"] == FlowResultType.FORM
    assert result5["errors"] == {
        "query": "query_invalid",
    }

    result5 = await hass.config_entries.flow.async_configure(
        result4["flow_id"],
        user_input=ENTRY_CONFIG,
    )

    assert result5["type"] == FlowResultType.CREATE_ENTRY
    assert result5["title"] == "Get Value"
    assert result5["options"] == {
        "name": "Get Value",
        "query": "SELECT 5 as value",
        "column": "value",
        "unit_of_measurement": "MiB",
        "device_class": SensorDeviceClass.DATA_SIZE,
        "state_class": SensorStateClass.TOTAL,
    }


async def test_flow_fails_invalid_column_name(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test config flow fails invalid column name."""
    result4 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result4["type"] == FlowResultType.FORM
    assert result4["step_id"] == "user"

    result5 = await hass.config_entries.flow.async_configure(
        result4["flow_id"],
        user_input=ENTRY_CONFIG_INVALID_COLUMN_NAME,
    )

    assert result5["type"] == FlowResultType.FORM
    assert result5["errors"] == {
        "column": "column_invalid",
    }

    result5 = await hass.config_entries.flow.async_configure(
        result4["flow_id"],
        user_input=ENTRY_CONFIG,
    )

    assert result5["type"] == FlowResultType.CREATE_ENTRY
    assert result5["title"] == "Get Value"
    assert result5["options"] == {
        "name": "Get Value",
        "query": "SELECT 5 as value",
        "column": "value",
        "unit_of_measurement": "MiB",
        "device_class": SensorDeviceClass.DATA_SIZE,
        "state_class": SensorStateClass.TOTAL,
    }


async def test_options_flow(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test options config flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            "db_url": "sqlite://",
            "name": "Get Value",
            "query": "SELECT 5 as value",
            "column": "value",
            "unit_of_measurement": "MiB",
            "device_class": SensorDeviceClass.DATA_SIZE,
            "state_class": SensorStateClass.TOTAL,
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.sql.async_setup_entry",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "db_url": "sqlite://",
            "query": "SELECT 5 as size",
            "column": "size",
            "unit_of_measurement": "MiB",
            "value_template": "{{ value }}",
            "device_class": SensorDeviceClass.DATA_SIZE,
            "state_class": SensorStateClass.TOTAL,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "name": "Get Value",
        "query": "SELECT 5 as size",
        "column": "size",
        "unit_of_measurement": "MiB",
        "value_template": "{{ value }}",
        "device_class": SensorDeviceClass.DATA_SIZE,
        "state_class": SensorStateClass.TOTAL,
    }


async def test_options_flow_name_previously_removed(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test options config flow where the name was missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            "db_url": "sqlite://",
            "query": "SELECT 5 as value",
            "column": "value",
            "unit_of_measurement": "MiB",
        },
        title="Get Value Title",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    with patch(
        "homeassistant.components.sql.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "db_url": "sqlite://",
                "query": "SELECT 5 as size",
                "column": "size",
                "unit_of_measurement": "MiB",
            },
        )
        await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 1
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "name": "Get Value Title",
        "query": "SELECT 5 as size",
        "column": "size",
        "unit_of_measurement": "MiB",
    }


async def test_options_flow_fails_db_url(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test options flow fails incorrect db url."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            "db_url": "sqlite://",
            "name": "Get Value",
            "query": "SELECT 5 as value",
            "column": "value",
            "unit_of_measurement": "MiB",
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.sql.async_setup_entry",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    with patch(
        "homeassistant.components.sql.config_flow.sqlalchemy.create_engine",
        side_effect=SQLAlchemyError("error_message"),
    ):
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "db_url": "sqlite://",
                "query": "SELECT 5 as size",
                "column": "size",
                "unit_of_measurement": "MiB",
            },
        )

    assert result2["errors"] == {"db_url": "db_url_invalid"}


async def test_options_flow_fails_invalid_query(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test options flow fails incorrect query and template."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            "db_url": "sqlite://",
            "name": "Get Value",
            "query": "SELECT 5 as value",
            "column": "value",
            "unit_of_measurement": "MiB",
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.sql.async_setup_entry",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=ENTRY_CONFIG_INVALID_QUERY_OPT,
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {
        "query": "query_invalid",
    }

    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=ENTRY_CONFIG_INVALID_QUERY_2_OPT,
    )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {
        "query": "query_invalid",
    }

    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=ENTRY_CONFIG_INVALID_QUERY_3_OPT,
    )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {
        "query": "query_invalid",
    }

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=ENTRY_CONFIG_QUERY_NO_READ_ONLY_OPT,
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {
        "query": "query_no_read_only",
    }

    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=ENTRY_CONFIG_QUERY_NO_READ_ONLY_CTE_OPT,
    )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {
        "query": "query_no_read_only",
    }

    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=ENTRY_CONFIG_MULTIPLE_QUERIES_OPT,
    )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {
        "query": "multiple_queries",
    }

    result4 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "db_url": "sqlite://",
            "query": "SELECT 5 as size",
            "column": "size",
            "unit_of_measurement": "MiB",
        },
    )

    assert result4["type"] == FlowResultType.CREATE_ENTRY
    assert result4["data"] == {
        "name": "Get Value",
        "query": "SELECT 5 as size",
        "column": "size",
        "unit_of_measurement": "MiB",
    }


async def test_options_flow_fails_invalid_column_name(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test options flow fails invalid column name."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            "name": "Get Value",
            "query": "SELECT 5 as value",
            "column": "value",
            "unit_of_measurement": "MiB",
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.sql.async_setup_entry",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=ENTRY_CONFIG_INVALID_COLUMN_NAME_OPT,
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {
        "column": "column_invalid",
    }

    result4 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "query": "SELECT 5 as value",
            "column": "value",
            "unit_of_measurement": "MiB",
        },
    )

    assert result4["type"] == FlowResultType.CREATE_ENTRY
    assert result4["data"] == {
        "name": "Get Value",
        "query": "SELECT 5 as value",
        "column": "value",
        "unit_of_measurement": "MiB",
    }


async def test_options_flow_db_url_empty(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test options config flow with leaving db_url empty."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            "db_url": "sqlite://",
            "name": "Get Value",
            "query": "SELECT 5 as value",
            "column": "value",
            "unit_of_measurement": "MiB",
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.sql.async_setup_entry",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    with patch(
        "homeassistant.components.sql.async_setup_entry",
        return_value=True,
    ), patch(
        "homeassistant.components.sql.config_flow.sqlalchemy.create_engine",
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "query": "SELECT 5 as size",
                "column": "size",
                "unit_of_measurement": "MiB",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "name": "Get Value",
        "query": "SELECT 5 as size",
        "column": "size",
        "unit_of_measurement": "MiB",
    }


async def test_full_flow_not_recorder_db(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test full config flow with not using recorder db."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.sql.async_setup_entry",
        return_value=True,
    ), patch(
        "homeassistant.components.sql.config_flow.sqlalchemy.create_engine",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "db_url": "sqlite://path/to/db.db",
                "name": "Get Value",
                "query": "SELECT 5 as value",
                "column": "value",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Get Value"
    assert result2["options"] == {
        "name": "Get Value",
        "db_url": "sqlite://path/to/db.db",
        "query": "SELECT 5 as value",
        "column": "value",
    }

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    with patch(
        "homeassistant.components.sql.async_setup_entry",
        return_value=True,
    ), patch(
        "homeassistant.components.sql.config_flow.sqlalchemy.create_engine",
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "query": "SELECT 5 as value",
                "db_url": "sqlite://path/to/db.db",
                "column": "value",
                "unit_of_measurement": "MiB",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "name": "Get Value",
        "db_url": "sqlite://path/to/db.db",
        "query": "SELECT 5 as value",
        "column": "value",
        "unit_of_measurement": "MiB",
    }

    # Need to test same again to mitigate issue with db_url removal
    result = await hass.config_entries.options.async_init(entry.entry_id)
    with patch(
        "homeassistant.components.sql.config_flow.sqlalchemy.create_engine",
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "query": "SELECT 5 as value",
                "db_url": "sqlite://path/to/db.db",
                "column": "value",
                "unit_of_measurement": "MB",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "name": "Get Value",
        "db_url": "sqlite://path/to/db.db",
        "query": "SELECT 5 as value",
        "column": "value",
        "unit_of_measurement": "MB",
    }

    assert entry.options == {
        "name": "Get Value",
        "db_url": "sqlite://path/to/db.db",
        "query": "SELECT 5 as value",
        "column": "value",
        "unit_of_measurement": "MB",
    }


async def test_device_state_class(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test we get the form."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            "name": "Get Value",
            "query": "SELECT 5 as value",
            "column": "value",
            "unit_of_measurement": "MiB",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    with patch(
        "homeassistant.components.sql.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "query": "SELECT 5 as value",
                "column": "value",
                "unit_of_measurement": "MiB",
                "device_class": SensorDeviceClass.DATA_SIZE,
                "state_class": SensorStateClass.TOTAL,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        "name": "Get Value",
        "query": "SELECT 5 as value",
        "column": "value",
        "unit_of_measurement": "MiB",
        "device_class": SensorDeviceClass.DATA_SIZE,
        "state_class": SensorStateClass.TOTAL,
    }

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    with patch(
        "homeassistant.components.sql.async_setup_entry",
        return_value=True,
    ):
        result3 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "query": "SELECT 5 as value",
                "column": "value",
                "unit_of_measurement": "MiB",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert "device_class" not in result3["data"]
    assert "state_class" not in result3["data"]
    assert result3["data"] == {
        "name": "Get Value",
        "query": "SELECT 5 as value",
        "column": "value",
        "unit_of_measurement": "MiB",
    }
