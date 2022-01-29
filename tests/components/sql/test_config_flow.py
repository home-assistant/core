"""Test the SQL config flow."""
from __future__ import annotations

from unittest.mock import patch

import sqlalchemy

from homeassistant import config_entries
from homeassistant.components.recorder import DEFAULT_DB_FILE, DEFAULT_URL
from homeassistant.components.sql.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from . import ENTRY_CONFIG, ENTRY_CONFIG_INVALID

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.sql.config_flow.sqlalchemy.create_engine",
    ), patch(
        "homeassistant.components.sql.config_flow.sqlalchemy.orm.scoped_session",
    ), patch(
        "homeassistant.components.sql.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            ENTRY_CONFIG,
        )
        await hass.async_block_till_done()

    db_url = DEFAULT_URL.format(hass_config_path=hass.config.path(DEFAULT_DB_FILE))

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Select size SQL query"
    assert result2["data"] == {
        "db_url": db_url,
        "query": "SELECT ROUND(page_count * page_size / 1024 / 1024, 1) as size FROM pragma_page_count(), pragma_page_size();",
        "column": "size",
        "unit_of_measurement": "MiB",
        "value_template": None,
        "name": "Select size SQL query",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_flow_success(hass: HomeAssistant) -> None:
    """Test a successful import of yaml."""

    with patch(
        "homeassistant.components.sql.config_flow.sqlalchemy.create_engine",
    ), patch(
        "homeassistant.components.sql.config_flow.sqlalchemy.orm.scoped_session",
    ), patch(
        "homeassistant.components.sql.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=ENTRY_CONFIG,
        )
        await hass.async_block_till_done()

    db_url = DEFAULT_URL.format(hass_config_path=hass.config.path(DEFAULT_DB_FILE))

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Select size SQL query"
    assert result2["data"] == {
        "db_url": db_url,
        "query": "SELECT ROUND(page_count * page_size / 1024 / 1024, 1) as size FROM pragma_page_count(), pragma_page_size();",
        "column": "size",
        "unit_of_measurement": "MiB",
        "value_template": None,
        "name": "Select size SQL query",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_flow_already_exist(hass: HomeAssistant) -> None:
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

    assert result3["type"] == RESULT_TYPE_ABORT
    assert result3["reason"] == "already_configured"


async def test_flow_fails_db_url(hass: HomeAssistant) -> None:
    """Test config flow fails incorrect db url."""
    result4 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result4["type"] == RESULT_TYPE_FORM
    assert result4["step_id"] == config_entries.SOURCE_USER

    with patch(
        "homeassistant.components.sql.config_flow.sqlalchemy.create_engine",
        side_effect=sqlalchemy.exc.SQLAlchemyError("error_message"),
    ), patch(
        "homeassistant.components.sql.config_flow.sqlalchemy.orm.scoped_session",
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result4["flow_id"],
            user_input=ENTRY_CONFIG,
        )

    assert result4["errors"] == {"db_url": "db_url_invalid"}


async def test_flow_fails_invalid_query_and_template(hass: HomeAssistant) -> None:
    """Test config flow fails incorrect db url."""
    result4 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result4["type"] == RESULT_TYPE_FORM
    assert result4["step_id"] == config_entries.SOURCE_USER

    with patch(
        "homeassistant.components.sql.config_flow.sqlalchemy.create_engine",
    ), patch(
        "homeassistant.components.sql.config_flow.sqlalchemy.orm.scoped_session",
    ):
        result5 = await hass.config_entries.flow.async_configure(
            result4["flow_id"],
            user_input=ENTRY_CONFIG_INVALID,
        )

    assert result5["type"] == RESULT_TYPE_FORM
    assert result5["errors"] == {
        "query": "query_invalid",
        "value_template": "value_template_invalid",
    }

    with patch(
        "homeassistant.components.sql.config_flow.sqlalchemy.create_engine",
    ), patch(
        "homeassistant.components.sql.config_flow.sqlalchemy.orm.scoped_session",
    ):
        result5 = await hass.config_entries.flow.async_configure(
            result4["flow_id"],
            user_input=ENTRY_CONFIG,
        )

    assert result5["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result5["title"] == "Select size SQL query"
