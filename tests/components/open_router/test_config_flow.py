"""Test the OpenRouter config flow."""

from unittest.mock import AsyncMock

import pytest
from python_open_router import OpenRouterError

from homeassistant.components.open_router.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigSubentry
from homeassistant.const import CONF_API_KEY, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration

from tests.common import MockConfigEntry


async def test_full_flow(
    hass: HomeAssistant,
    mock_open_router_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the full config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "bla"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_API_KEY: "bla"}


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (OpenRouterError("exception"), "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_open_router_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test we handle errors from the OpenRouter API."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_open_router_client.get_key_data.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "bla"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_open_router_client.get_key_data.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "bla"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate_entry(
    hass: HomeAssistant,
    mock_open_router_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test aborting the flow if an entry already exists."""

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "bla"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_create_conversation_agent(
    hass: HomeAssistant,
    mock_open_router_client: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating a conversation agent."""

    mock_config_entry.add_to_hass(hass)

    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "conversation"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]
    assert result["step_id"] == "user"

    assert result["data_schema"].schema["model"].config["options"] == [
        {"value": "gpt-3.5-turbo", "label": "GPT-3.5 Turbo"},
    ]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_MODEL: "gpt-3.5-turbo"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry_id = list(mock_config_entry.subentries)[0]
    assert (
        ConfigSubentry(
            data={CONF_MODEL: "gpt-3.5-turbo"},
            subentry_id=subentry_id,
            subentry_type="conversation",
            title="GPT-3.5 Turbo",
            unique_id=None,
        )
        in mock_config_entry.subentries.values()
    )
