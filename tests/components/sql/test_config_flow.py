"""Test the SQL config flow."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError
from syrupy.assertion import SnapshotAssertion

from homeassistant import config_entries
from homeassistant.components.recorder import CONF_DB_URL
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.components.sql.const import (
    CONF_ADVANCED_OPTIONS,
    CONF_COLUMN_NAME,
    CONF_QUERY,
    DOMAIN,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData

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
    ENTRY_CONFIG_WITH_BROKEN_QUERY_TEMPLATE,
    ENTRY_CONFIG_WITH_BROKEN_QUERY_TEMPLATE_OPT,
    ENTRY_CONFIG_WITH_QUERY_TEMPLATE,
    ENTRY_CONFIG_WITH_VALUE_TEMPLATE,
    init_integration,
)

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator

pytestmark = pytest.mark.usefixtures("recorder_mock")

DATA_CONFIG = {CONF_NAME: "Get Value"}
DATA_CONFIG_DB = {CONF_NAME: "Get Value", CONF_DB_URL: "sqlite://"}
OPTIONS_DATA_CONFIG = {}


@pytest.mark.parametrize(
    ("data_config", "result_config"),
    [
        (DATA_CONFIG, OPTIONS_DATA_CONFIG),
        (DATA_CONFIG_DB, OPTIONS_DATA_CONFIG),
    ],
)
async def test_form_simple(
    mock_setup_entry: AsyncMock,
    hass: HomeAssistant,
    data_config: dict[str, Any],
    result_config: dict[str, Any],
) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        data_config,
    )
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        ENTRY_CONFIG,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Get Value"
    assert result["data"] == result_config
    assert result["options"] == {
        CONF_QUERY: "SELECT 5 as value",
        CONF_COLUMN_NAME: "value",
        CONF_ADVANCED_OPTIONS: {
            CONF_UNIT_OF_MEASUREMENT: "MiB",
            CONF_DEVICE_CLASS: SensorDeviceClass.DATA_SIZE,
            CONF_STATE_CLASS: SensorStateClass.TOTAL,
        },
    }


async def test_form_with_query_template(hass: HomeAssistant) -> None:
    """Test for with query template."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.sql.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            DATA_CONFIG,
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            ENTRY_CONFIG_WITH_QUERY_TEMPLATE,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Get Value"
    assert result["options"] == {
        CONF_QUERY: "SELECT {% if states('sensor.input1')=='on' %} 5 {% else %} 6 {% endif %} as value",
        CONF_COLUMN_NAME: "value",
        CONF_ADVANCED_OPTIONS: {
            CONF_UNIT_OF_MEASUREMENT: "MiB",
            CONF_VALUE_TEMPLATE: "{{ value }}",
        },
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_with_broken_query_template(hass: HomeAssistant) -> None:
    """Test form with broken query template."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        DATA_CONFIG,
    )
    message = re.escape("Schema validation failed @ data['query']")
    with pytest.raises(InvalidData, match=message):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            ENTRY_CONFIG_WITH_BROKEN_QUERY_TEMPLATE,
        )

    with patch(
        "homeassistant.components.sql.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            ENTRY_CONFIG_WITH_QUERY_TEMPLATE,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Get Value"
    assert result["options"] == {
        CONF_QUERY: "SELECT {% if states('sensor.input1')=='on' %} 5 {% else %} 6 {% endif %} as value",
        CONF_COLUMN_NAME: "value",
        CONF_ADVANCED_OPTIONS: {
            CONF_UNIT_OF_MEASUREMENT: "MiB",
            CONF_VALUE_TEMPLATE: "{{ value }}",
        },
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_with_value_template(
    mock_setup_entry: AsyncMock, hass: HomeAssistant
) -> None:
    """Test for with value template."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        DATA_CONFIG,
    )
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        ENTRY_CONFIG_WITH_VALUE_TEMPLATE,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Get Value"
    assert result["data"] == {}
    assert result["options"] == {
        CONF_QUERY: "SELECT 5 as value",
        CONF_COLUMN_NAME: "value",
        CONF_ADVANCED_OPTIONS: {
            CONF_UNIT_OF_MEASUREMENT: "MiB",
            CONF_VALUE_TEMPLATE: "{{ value }}",
        },
    }


async def test_flow_fails_db_url(
    mock_setup_entry: AsyncMock, hass: HomeAssistant
) -> None:
    """Test config flow fails incorrect db url."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    with patch(
        "homeassistant.components.sql.config_flow.sqlalchemy.create_engine",
        side_effect=SQLAlchemyError("error_message"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=DATA_CONFIG,
        )

    assert result["errors"] == {CONF_DB_URL: "db_url_invalid"}


async def test_flow_fails_invalid_query(
    mock_setup_entry: AsyncMock, hass: HomeAssistant
) -> None:
    """Test config flow fails incorrect db url."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=DATA_CONFIG,
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=ENTRY_CONFIG_INVALID_QUERY,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        CONF_QUERY: "query_invalid",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=ENTRY_CONFIG_INVALID_QUERY_2,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        CONF_QUERY: "query_no_read_only",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=ENTRY_CONFIG_INVALID_QUERY_3,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        CONF_QUERY: "query_no_read_only",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=ENTRY_CONFIG_QUERY_NO_READ_ONLY,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        CONF_QUERY: "query_no_read_only",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=ENTRY_CONFIG_QUERY_NO_READ_ONLY_CTE,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        CONF_QUERY: "query_no_read_only",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=ENTRY_CONFIG_MULTIPLE_QUERIES,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        CONF_QUERY: "multiple_queries",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=ENTRY_CONFIG_NO_RESULTS,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        CONF_QUERY: "query_invalid",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=ENTRY_CONFIG,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Get Value"
    assert result["data"] == {}
    assert result["options"] == {
        CONF_QUERY: "SELECT 5 as value",
        CONF_COLUMN_NAME: "value",
        CONF_ADVANCED_OPTIONS: {
            CONF_UNIT_OF_MEASUREMENT: "MiB",
            CONF_DEVICE_CLASS: SensorDeviceClass.DATA_SIZE,
            CONF_STATE_CLASS: SensorStateClass.TOTAL,
        },
    }


async def test_flow_fails_invalid_column_name(
    mock_setup_entry: AsyncMock, hass: HomeAssistant
) -> None:
    """Test config flow fails invalid column name."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=DATA_CONFIG,
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=ENTRY_CONFIG_INVALID_COLUMN_NAME,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        CONF_COLUMN_NAME: "column_invalid",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=ENTRY_CONFIG,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Get Value"
    assert result["data"] == {}
    assert result["options"] == {
        CONF_QUERY: "SELECT 5 as value",
        CONF_COLUMN_NAME: "value",
        CONF_ADVANCED_OPTIONS: {
            CONF_UNIT_OF_MEASUREMENT: "MiB",
            CONF_DEVICE_CLASS: SensorDeviceClass.DATA_SIZE,
            CONF_STATE_CLASS: SensorStateClass.TOTAL,
        },
    }


async def test_options_flow(mock_setup_entry: AsyncMock, hass: HomeAssistant) -> None:
    """Test options config flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=OPTIONS_DATA_CONFIG,
        options={
            CONF_QUERY: "SELECT 5 as value",
            CONF_COLUMN_NAME: "value",
            CONF_ADVANCED_OPTIONS: {
                CONF_UNIT_OF_MEASUREMENT: "MiB",
                CONF_DEVICE_CLASS: SensorDeviceClass.DATA_SIZE,
                CONF_STATE_CLASS: SensorStateClass.TOTAL,
            },
        },
        version=2,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_QUERY: "SELECT 5 as size",
            CONF_COLUMN_NAME: "size",
            CONF_ADVANCED_OPTIONS: {
                CONF_UNIT_OF_MEASUREMENT: "MiB",
                CONF_VALUE_TEMPLATE: "{{ value }}",
                CONF_DEVICE_CLASS: SensorDeviceClass.DATA_SIZE,
                CONF_STATE_CLASS: SensorStateClass.TOTAL,
            },
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_QUERY: "SELECT 5 as size",
        CONF_COLUMN_NAME: "size",
        CONF_ADVANCED_OPTIONS: {
            CONF_UNIT_OF_MEASUREMENT: "MiB",
            CONF_VALUE_TEMPLATE: "{{ value }}",
            CONF_DEVICE_CLASS: SensorDeviceClass.DATA_SIZE,
            CONF_STATE_CLASS: SensorStateClass.TOTAL,
        },
    }


async def test_options_flow_name_previously_removed(
    mock_setup_entry: AsyncMock, hass: HomeAssistant
) -> None:
    """Test options config flow where the name was missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=OPTIONS_DATA_CONFIG,
        options={
            CONF_QUERY: "SELECT 5 as value",
            CONF_COLUMN_NAME: "value",
            CONF_ADVANCED_OPTIONS: {
                CONF_UNIT_OF_MEASUREMENT: "MiB",
            },
        },
        version=2,
        title="Get Value Title",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_QUERY: "SELECT 5 as size",
            CONF_COLUMN_NAME: "size",
            CONF_ADVANCED_OPTIONS: {
                CONF_UNIT_OF_MEASUREMENT: "MiB",
            },
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_QUERY: "SELECT 5 as size",
        CONF_COLUMN_NAME: "size",
        CONF_ADVANCED_OPTIONS: {
            CONF_UNIT_OF_MEASUREMENT: "MiB",
        },
    }


async def test_options_flow_fails_db_url(
    mock_setup_entry: AsyncMock, hass: HomeAssistant
) -> None:
    """Test options flow fails incorrect db url."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=OPTIONS_DATA_CONFIG,
        options={
            CONF_QUERY: "SELECT 5 as value",
            CONF_COLUMN_NAME: "value",
            CONF_ADVANCED_OPTIONS: {
                CONF_UNIT_OF_MEASUREMENT: "MiB",
            },
        },
        version=2,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    with patch(
        "homeassistant.components.sql.config_flow.sqlalchemy.create_engine",
        side_effect=SQLAlchemyError("error_message"),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_QUERY: "SELECT 5 as size",
                CONF_COLUMN_NAME: "size",
                CONF_ADVANCED_OPTIONS: {
                    CONF_UNIT_OF_MEASUREMENT: "MiB",
                },
            },
        )

    assert result["errors"] == {CONF_DB_URL: "db_url_invalid"}


async def test_options_flow_fails_invalid_query(
    mock_setup_entry: AsyncMock, hass: HomeAssistant
) -> None:
    """Test options flow fails incorrect query and template."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=OPTIONS_DATA_CONFIG,
        options={
            CONF_QUERY: "SELECT 5 as value",
            CONF_COLUMN_NAME: "value",
            CONF_ADVANCED_OPTIONS: {
                CONF_UNIT_OF_MEASUREMENT: "MiB",
            },
        },
        version=2,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=ENTRY_CONFIG_INVALID_QUERY_OPT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        CONF_QUERY: "query_invalid",
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=ENTRY_CONFIG_INVALID_QUERY_2_OPT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        CONF_QUERY: "query_no_read_only",
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=ENTRY_CONFIG_INVALID_QUERY_3_OPT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        CONF_QUERY: "query_no_read_only",
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=ENTRY_CONFIG_QUERY_NO_READ_ONLY_OPT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        CONF_QUERY: "query_no_read_only",
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=ENTRY_CONFIG_QUERY_NO_READ_ONLY_CTE_OPT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        CONF_QUERY: "query_no_read_only",
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=ENTRY_CONFIG_MULTIPLE_QUERIES_OPT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        CONF_QUERY: "multiple_queries",
    }

    message = re.escape("Schema validation failed @ data['query']")
    with pytest.raises(InvalidData, match=message):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=ENTRY_CONFIG_WITH_BROKEN_QUERY_TEMPLATE_OPT,
        )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_QUERY: "SELECT 5 as size",
            CONF_COLUMN_NAME: "size",
            CONF_ADVANCED_OPTIONS: {
                CONF_UNIT_OF_MEASUREMENT: "MiB",
            },
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_QUERY: "SELECT 5 as size",
        CONF_COLUMN_NAME: "size",
        CONF_ADVANCED_OPTIONS: {
            CONF_UNIT_OF_MEASUREMENT: "MiB",
        },
    }


async def test_options_flow_fails_invalid_column_name(
    mock_setup_entry: AsyncMock, hass: HomeAssistant
) -> None:
    """Test options flow fails invalid column name."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=OPTIONS_DATA_CONFIG,
        options={
            CONF_QUERY: "SELECT 5 as value",
            CONF_COLUMN_NAME: "value",
            CONF_ADVANCED_OPTIONS: {
                CONF_UNIT_OF_MEASUREMENT: "MiB",
            },
        },
        version=2,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=ENTRY_CONFIG_INVALID_COLUMN_NAME_OPT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        CONF_COLUMN_NAME: "column_invalid",
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_QUERY: "SELECT 5 as value",
            CONF_COLUMN_NAME: "value",
            CONF_ADVANCED_OPTIONS: {
                CONF_UNIT_OF_MEASUREMENT: "MiB",
            },
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_QUERY: "SELECT 5 as value",
        CONF_COLUMN_NAME: "value",
        CONF_ADVANCED_OPTIONS: {
            CONF_UNIT_OF_MEASUREMENT: "MiB",
        },
    }


async def test_options_flow_db_url_empty(
    mock_setup_entry: AsyncMock, hass: HomeAssistant
) -> None:
    """Test options config flow with leaving db_url empty."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=OPTIONS_DATA_CONFIG,
        options={
            CONF_QUERY: "SELECT 5 as value",
            CONF_COLUMN_NAME: "value",
            CONF_ADVANCED_OPTIONS: {
                CONF_UNIT_OF_MEASUREMENT: "MiB",
            },
        },
        version=2,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_QUERY: "SELECT 5 as size",
            CONF_COLUMN_NAME: "size",
            CONF_ADVANCED_OPTIONS: {
                CONF_UNIT_OF_MEASUREMENT: "MiB",
            },
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_QUERY: "SELECT 5 as size",
        CONF_COLUMN_NAME: "size",
        CONF_ADVANCED_OPTIONS: {
            CONF_UNIT_OF_MEASUREMENT: "MiB",
        },
    }


async def test_full_flow_not_recorder_db(
    mock_setup_entry: AsyncMock,
    hass: HomeAssistant,
    tmp_path: Path,
) -> None:
    """Test full config flow with not using recorder db."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    db_path = tmp_path / "db.db"
    db_path_str = f"sqlite:///{db_path}"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DB_URL: db_path_str,
            CONF_NAME: "Get Value",
        },
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_QUERY: "SELECT 5 as value",
            CONF_COLUMN_NAME: "value",
            CONF_ADVANCED_OPTIONS: {},
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Get Value"
    assert result["data"] == {CONF_DB_URL: db_path_str}
    assert result["options"] == {
        CONF_QUERY: "SELECT 5 as value",
        CONF_COLUMN_NAME: "value",
        CONF_ADVANCED_OPTIONS: {},
    }

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_QUERY: "SELECT 5 as value",
            CONF_COLUMN_NAME: "value",
            CONF_ADVANCED_OPTIONS: {
                CONF_UNIT_OF_MEASUREMENT: "MiB",
            },
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_QUERY: "SELECT 5 as value",
        CONF_COLUMN_NAME: "value",
        CONF_ADVANCED_OPTIONS: {
            CONF_UNIT_OF_MEASUREMENT: "MiB",
        },
    }


async def test_device_state_class(
    mock_setup_entry: AsyncMock, hass: HomeAssistant
) -> None:
    """Test we get the form."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=OPTIONS_DATA_CONFIG,
        options={
            CONF_QUERY: "SELECT 5 as value",
            CONF_COLUMN_NAME: "value",
            CONF_ADVANCED_OPTIONS: {
                CONF_UNIT_OF_MEASUREMENT: "MiB",
            },
        },
        version=2,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_QUERY: "SELECT 5 as value",
            CONF_COLUMN_NAME: "value",
            CONF_ADVANCED_OPTIONS: {
                CONF_UNIT_OF_MEASUREMENT: "MiB",
                CONF_DEVICE_CLASS: SensorDeviceClass.DATA_SIZE,
                CONF_STATE_CLASS: SensorStateClass.TOTAL,
            },
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_QUERY: "SELECT 5 as value",
        CONF_COLUMN_NAME: "value",
        CONF_ADVANCED_OPTIONS: {
            CONF_UNIT_OF_MEASUREMENT: "MiB",
            CONF_DEVICE_CLASS: SensorDeviceClass.DATA_SIZE,
            CONF_STATE_CLASS: SensorStateClass.TOTAL,
        },
    }

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_QUERY: "SELECT 5 as value",
            CONF_COLUMN_NAME: "value",
            CONF_ADVANCED_OPTIONS: {
                CONF_UNIT_OF_MEASUREMENT: "MiB",
            },
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_DEVICE_CLASS not in result["data"]
    assert CONF_STATE_CLASS not in result["data"]
    assert result["data"] == {
        CONF_QUERY: "SELECT 5 as value",
        CONF_COLUMN_NAME: "value",
        CONF_ADVANCED_OPTIONS: {
            CONF_UNIT_OF_MEASUREMENT: "MiB",
        },
    }


@pytest.mark.parametrize(
    "user_input",
    [
        (
            {
                CONF_NAME: "Get Value",
                CONF_QUERY: "SELECT 5 as value",
                CONF_COLUMN_NAME: "value",
                CONF_UNIT_OF_MEASUREMENT: "MiB",
                CONF_DEVICE_CLASS: SensorDeviceClass.DATA_SIZE,
                CONF_STATE_CLASS: SensorStateClass.TOTAL,
            }
        ),
        (
            {
                CONF_NAME: "Get Value",
                CONF_QUERY: "SELECT 5 as value",
                CONF_COLUMN_NAME: "state",
                CONF_UNIT_OF_MEASUREMENT: "MiB",
                CONF_DEVICE_CLASS: SensorDeviceClass.DATA_SIZE,
                CONF_STATE_CLASS: SensorStateClass.TOTAL,
            }
        ),
        (
            {
                CONF_NAME: "Get Value",
                CONF_QUERY: "SELECT 5 as value",
            }
        ),
        (
            {
                CONF_NAME: "Get Value",
                CONF_QUERY: "SELECT 5 as value",
                CONF_COLUMN_NAME: "value",
                CONF_VALUE_TEMPLATE: "{{ value }}",
                CONF_UNIT_OF_MEASUREMENT: "MiB",
                CONF_DEVICE_CLASS: SensorDeviceClass.DATA_SIZE,
                CONF_STATE_CLASS: SensorStateClass.TOTAL,
            }
        ),
        (
            {
                CONF_NAME: "Get Value",
                CONF_QUERY: "SELECT 5 as value",
                CONF_COLUMN_NAME: "value",
                CONF_VALUE_TEMPLATE: "{{ value",
                CONF_UNIT_OF_MEASUREMENT: "MiB",
                CONF_DEVICE_CLASS: SensorDeviceClass.DATA_SIZE,
                CONF_STATE_CLASS: SensorStateClass.TOTAL,
            }
        ),
    ],
    ids=(
        "success",
        "incorrect_column",
        "missing_column",
        "with_value_template",
        "with_value_template_invalid",
    ),
)
async def test_config_flow_preview(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    user_input: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the config flow preview."""
    client = await hass_ws_client(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    assert result["preview"] == "sql"

    await client.send_json_auto_id(
        {
            "type": "sql/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "config_flow",
            "user_input": user_input,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    msg = await client.receive_json()
    assert msg["event"] == snapshot
    assert len(hass.states.async_all()) == 0


async def test_config_flow_preview_no_database(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the config flow preview with no database."""
    client = await hass_ws_client(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch("homeassistant.components.sql.config_flow.validate_db_connection"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DB_URL: "sqlite://not_exist.local", CONF_NAME: "Get Value"},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "options"
    assert result["errors"] == {}
    assert result["preview"] == "sql"

    await client.send_json_auto_id(
        {
            "type": "sql/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "config_flow",
            "user_input": {
                CONF_QUERY: "SELECT 5 as value",
                CONF_COLUMN_NAME: "value",
                CONF_ADVANCED_OPTIONS: {
                    CONF_UNIT_OF_MEASUREMENT: "MiB",
                    CONF_DEVICE_CLASS: SensorDeviceClass.DATA_SIZE,
                    CONF_STATE_CLASS: SensorStateClass.TOTAL,
                },
            },
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    msg = await client.receive_json()
    print(msg)
    assert msg["event"] == snapshot
    assert False


async def test_options_flow_preview(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the options flow preview."""
    client = await hass_ws_client(hass)

    # Setup the config entry
    config_entry = await init_integration(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["preview"] == "sql"

    await client.send_json_auto_id(
        {
            "type": "sql/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "options_flow",
            "user_input": {
                CONF_QUERY: "SELECT 6 as value",
                CONF_COLUMN_NAME: "value",
                CONF_ADVANCED_OPTIONS: {
                    CONF_UNIT_OF_MEASUREMENT: "MiB",
                    CONF_DEVICE_CLASS: SensorDeviceClass.DATA_SIZE,
                    CONF_STATE_CLASS: SensorStateClass.TOTAL,
                },
            },
        }
    )

    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    msg = await client.receive_json()
    assert msg["event"] == snapshot
    assert len(hass.states.async_all()) == 1


async def test_options_flow_sensor_preview_config_entry_removed(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the option flow preview where the config entry is removed."""
    client = await hass_ws_client(hass)

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_NAME: "Get Value",
            CONF_QUERY: "SELECT 5 as value",
            CONF_COLUMN_NAME: "value",
            CONF_UNIT_OF_MEASUREMENT: "MiB",
            CONF_DEVICE_CLASS: SensorDeviceClass.DATA_SIZE,
            CONF_STATE_CLASS: SensorStateClass.TOTAL,
        },
        title="Get Value",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["preview"] == "sql"

    await hass.config_entries.async_remove(config_entry.entry_id)

    await client.send_json_auto_id(
        {
            "type": "sql/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "options_flow",
            "user_input": {
                CONF_QUERY: "SELECT 6 as value",
                CONF_COLUMN_NAME: "value",
                CONF_UNIT_OF_MEASUREMENT: "MiB",
                CONF_DEVICE_CLASS: SensorDeviceClass.DATA_SIZE,
                CONF_STATE_CLASS: SensorStateClass.TOTAL,
            },
        }
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"] == {
        "code": "home_assistant_error",
        "message": "Config entry not found",
    }
