"""Test the Traccar Server config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock

import pytest
from pytraccar import TraccarAuthenticationException, TraccarException

from homeassistant import config_entries
from homeassistant.components.traccar_server.const import (
    CONF_CUSTOM_ATTRIBUTES,
    CONF_EVENTS,
    CONF_MAX_ACCURACY,
    CONF_SKIP_ACCURACY_FILTER_FOR,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(
    hass: HomeAssistant,
    mock_traccar_api_client: Generator[AsyncMock],
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "1.1.1.1:8082"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: "8082",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        CONF_SSL: False,
        CONF_VERIFY_SSL: True,
    }
    assert result["result"].state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (TraccarException, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_cannot_connect(
    hass: HomeAssistant,
    side_effect: Exception,
    error: str,
    mock_traccar_api_client: Generator[AsyncMock],
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_traccar_api_client.get_server.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_traccar_api_client.get_server.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "1.1.1.1:8082"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: "8082",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        CONF_SSL: False,
        CONF_VERIFY_SSL: True,
    }

    assert result["result"].state is ConfigEntryState.LOADED


async def test_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_traccar_api_client: Generator[AsyncMock],
) -> None:
    """Test options flow."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.options.get(CONF_MAX_ACCURACY) == 5.0

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_MAX_ACCURACY: 2.0},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {
        CONF_MAX_ACCURACY: 2.0,
        CONF_EVENTS: [],
        CONF_CUSTOM_ATTRIBUTES: [],
        CONF_SKIP_ACCURACY_FILTER_FOR: [],
    }


async def test_abort_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_traccar_api_client: Generator[AsyncMock],
) -> None:
    """Test abort for existing server."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_PORT: "8082",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_traccar_api_client: Generator[AsyncMock],
) -> None:
    """Test reauth flow."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "new-username",
            CONF_PASSWORD: "new-password",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    # Verify the config entry was updated
    assert mock_config_entry.data[CONF_USERNAME] == "new-username"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (TraccarAuthenticationException, "invalid_auth"),
        (TraccarException, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_traccar_api_client: Generator[AsyncMock],
    side_effect: Exception,
    error: str,
) -> None:
    """Test reauth flow with errors."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )

    mock_traccar_api_client.get_server.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "new-username",
            CONF_PASSWORD: "new-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    # Test recovery after error
    mock_traccar_api_client.get_server.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "new-username",
            CONF_PASSWORD: "new-password",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
