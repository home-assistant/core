"""Tests for the Meraki config flow."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.meraki.const import CONF_ORGANIZATION_ID, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import api_error
from .conftest import API_KEY, ORGANIZATION_ID


@pytest.mark.usefixtures("mock_setup_entry", "mock_meraki_client")
async def test_full_flow(hass: HomeAssistant) -> None:
    """Test an API key with one organization."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home Lab"
    assert result["data"] == {
        CONF_API_KEY: API_KEY,
        CONF_ORGANIZATION_ID: ORGANIZATION_ID,
    }
    assert result["result"].unique_id == ORGANIZATION_ID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_multiple_organizations(
    hass: HomeAssistant, mock_meraki_client: MagicMock
) -> None:
    """Test choosing one of several organizations."""
    mock_meraki_client.organizations.getOrganizations.return_value = [
        {"id": ORGANIZATION_ID, "name": "Home Lab"},
        {"id": "999", "name": "Office"},
    ]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "organization"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ORGANIZATION_ID: "999"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Office"
    assert result["result"].unique_id == "999"


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("side_effect", "return_value", "error"),
    [
        pytest.param(api_error(401), None, "invalid_auth", id="invalid_auth"),
        pytest.param(api_error(503), None, "cannot_connect", id="cannot_connect"),
        pytest.param(RuntimeError, None, "unknown", id="unknown"),
        pytest.param(None, [], "no_organizations", id="no_organizations"),
    ],
)
async def test_user_errors(
    hass: HomeAssistant,
    mock_meraki_client: MagicMock,
    side_effect: Exception | type[Exception] | None,
    return_value: list | None,
    error: str,
) -> None:
    """Test errors are shown and the flow can recover."""
    get_organizations: AsyncMock = mock_meraki_client.organizations.getOrganizations
    original = get_organizations.return_value
    get_organizations.side_effect = side_effect
    get_organizations.return_value = return_value
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    get_organizations.side_effect = None
    get_organizations.return_value = original
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_meraki_client")
async def test_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test an organization can only be added once."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
