"""Tests for the Emby config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.emby.config_flow import CannotConnect, InvalidAuth
from homeassistant.components.emby.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_API_KEY, TEST_HOST, TEST_PORT, TEST_SERVER_ID

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

USER_INPUT = {
    CONF_HOST: TEST_HOST,
    CONF_API_KEY: TEST_API_KEY,
    CONF_PORT: TEST_PORT,
    CONF_SSL: False,
}


async def test_user_flow_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test a successful user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.emby.config_flow._validate_connection",
        return_value=TEST_SERVER_ID,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_HOST
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_PORT: TEST_PORT,
        CONF_API_KEY: TEST_API_KEY,
        CONF_SSL: False,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_default_port_http(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test that default HTTP port is used when no port is specified."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.emby.config_flow._validate_connection",
        return_value=TEST_SERVER_ID,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: TEST_HOST,
                CONF_API_KEY: TEST_API_KEY,
                CONF_SSL: False,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PORT] == 8096


async def test_user_flow_default_port_ssl(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test that default SSL port is used when SSL is enabled and no port is specified."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.emby.config_flow._validate_connection",
        return_value=TEST_SERVER_ID,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: TEST_HOST,
                CONF_API_KEY: TEST_API_KEY,
                CONF_SSL: True,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PORT] == 8920


async def test_user_flow_cannot_connect(
    hass: HomeAssistant,
) -> None:
    """Test handling a connection failure in the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.emby.config_flow._validate_connection",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Verify the user can recover by fixing the input
    with patch(
        "homeassistant.components.emby.config_flow._validate_connection",
        return_value=TEST_SERVER_ID,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_invalid_auth(
    hass: HomeAssistant,
) -> None:
    """Test handling an authentication failure in the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.emby.config_flow._validate_connection",
        side_effect=InvalidAuth,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_unknown_error(
    hass: HomeAssistant,
) -> None:
    """Test handling an unexpected error in the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.emby.config_flow._validate_connection",
        side_effect=Exception("Unexpected"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_user_flow_duplicate_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a duplicate entry is aborted."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.emby.config_flow._validate_connection",
        return_value=TEST_SERVER_ID,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
