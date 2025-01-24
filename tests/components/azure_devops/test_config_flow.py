"""Test the Azure DevOps config flow."""

from unittest.mock import AsyncMock

import aiohttp

from homeassistant import config_entries
from homeassistant.components.azure_devops.const import CONF_ORG, CONF_PROJECT, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import FIXTURE_REAUTH_INPUT, FIXTURE_USER_INPUT

from tests.common import MockConfigEntry


async def test_show_user_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_authorization_error(
    hass: HomeAssistant,
    mock_devops_client: AsyncMock,
) -> None:
    """Test we show user form on Azure DevOps authorization error."""
    mock_devops_client.authorize.return_value = False
    mock_devops_client.authorized = False

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        FIXTURE_USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_reauth_authorization_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_devops_client: AsyncMock,
) -> None:
    """Test we show user form on Azure DevOps authorization error."""
    mock_config_entry.add_to_hass(hass)
    mock_devops_client.authorize.return_value = False
    mock_devops_client.authorized = False

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        FIXTURE_REAUTH_INPUT,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "reauth_confirm"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_connection_error(
    hass: HomeAssistant,
    mock_devops_client: AsyncMock,
) -> None:
    """Test we show user form on Azure DevOps connection error."""
    mock_devops_client.authorize.side_effect = aiohttp.ClientError
    mock_devops_client.authorized = False

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        FIXTURE_USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_reauth_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_devops_client: AsyncMock,
) -> None:
    """Test we show user form on Azure DevOps connection error."""
    mock_config_entry.add_to_hass(hass)
    mock_devops_client.authorize.side_effect = aiohttp.ClientError
    mock_devops_client.authorized = False

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        FIXTURE_REAUTH_INPUT,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "reauth_confirm"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_project_error(
    hass: HomeAssistant,
    mock_devops_client: AsyncMock,
) -> None:
    """Test we show user form on Azure DevOps connection error."""
    mock_devops_client.authorize.return_value = True
    mock_devops_client.authorized = True
    mock_devops_client.get_project.return_value = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        FIXTURE_USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "project_error"}


async def test_reauth_project_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_devops_client: AsyncMock,
) -> None:
    """Test we show user form on Azure DevOps project error."""
    mock_devops_client.authorize.return_value = True
    mock_devops_client.authorized = True
    mock_devops_client.get_project.return_value = None

    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        FIXTURE_REAUTH_INPUT,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "reauth_confirm"
    assert result2["errors"] == {"base": "project_error"}


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_devops_client: AsyncMock,
) -> None:
    """Test reauth works."""
    mock_devops_client.authorize.return_value = False
    mock_devops_client.authorized = False

    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_devops_client.authorize.return_value = True
    mock_devops_client.authorized = True

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        FIXTURE_REAUTH_INPUT,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"


async def test_full_flow_implementation(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_devops_client: AsyncMock,
) -> None:
    """Test registering an integration and finishing flow works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        FIXTURE_USER_INPUT,
    )
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert (
        result2["title"]
        == f"{FIXTURE_USER_INPUT[CONF_ORG]}/{FIXTURE_USER_INPUT[CONF_PROJECT]}"
    )
    assert result2["data"][CONF_ORG] == FIXTURE_USER_INPUT[CONF_ORG]
    assert result2["data"][CONF_PROJECT] == FIXTURE_USER_INPUT[CONF_PROJECT]
