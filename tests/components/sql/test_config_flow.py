"""Test the SQL config flow."""
from __future__ import annotations

from unittest.mock import patch

from sqlalchemy.exc import SQLAlchemyError

from homeassistant import config_entries
from homeassistant.components.sql.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    ENTRY_CONFIG,
    ENTRY_CONFIG_INVALID_QUERY,
    ENTRY_CONFIG_INVALID_QUERY_OPT,
    ENTRY_CONFIG_NO_RESULTS,
)

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant, recorder_mock) -> None:
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
        "db_url": "sqlite://",
        "name": "Get Value",
        "query": "SELECT 5 as value",
        "column": "value",
        "unit_of_measurement": "MiB",
        "value_template": None,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_flow_success(hass: HomeAssistant, recorder_mock) -> None:
    """Test a successful import of yaml."""

    with patch(
        "homeassistant.components.sql.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=ENTRY_CONFIG,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Get Value"
    assert result2["options"] == {
        "db_url": "sqlite://",
        "name": "Get Value",
        "query": "SELECT 5 as value",
        "column": "value",
        "unit_of_measurement": "MiB",
        "value_template": None,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_flow_already_exist(hass: HomeAssistant, recorder_mock) -> None:
    """Test import of yaml already exist."""

    MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_CONFIG,
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.sql.async_setup_entry",
        return_value=True,
    ):
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=ENTRY_CONFIG,
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.ABORT
    assert result3["reason"] == "already_configured"


async def test_flow_fails_db_url(hass: HomeAssistant, recorder_mock) -> None:
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


async def test_flow_fails_invalid_query(hass: HomeAssistant, recorder_mock) -> None:
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
        "db_url": "sqlite://",
        "name": "Get Value",
        "query": "SELECT 5 as value",
        "column": "value",
        "unit_of_measurement": "MiB",
        "value_template": None,
    }


async def test_options_flow(hass: HomeAssistant, recorder_mock) -> None:
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
            "value_template": None,
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
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "name": "Get Value",
        "db_url": "sqlite://",
        "query": "SELECT 5 as size",
        "column": "size",
        "value_template": None,
        "unit_of_measurement": "MiB",
    }


async def test_options_flow_name_previously_removed(
    hass: HomeAssistant, recorder_mock
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
            "value_template": None,
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
        "db_url": "sqlite://",
        "query": "SELECT 5 as size",
        "column": "size",
        "value_template": None,
        "unit_of_measurement": "MiB",
    }


async def test_options_flow_fails_db_url(hass: HomeAssistant, recorder_mock) -> None:
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
            "value_template": None,
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
    hass: HomeAssistant, recorder_mock
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
            "value_template": None,
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
        "value_template": None,
        "db_url": "sqlite://",
        "query": "SELECT 5 as size",
        "column": "size",
        "unit_of_measurement": "MiB",
    }


async def test_options_flow_db_url_empty(hass: HomeAssistant, recorder_mock) -> None:
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
            "value_template": None,
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
        "db_url": "sqlite://",
        "query": "SELECT 5 as size",
        "column": "size",
        "value_template": None,
        "unit_of_measurement": "MiB",
    }
