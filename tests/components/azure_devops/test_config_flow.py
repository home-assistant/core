"""Test the Azure DevOps config flow."""
from unittest.mock import patch

import aiohttp

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.azure_devops.const import (
    CONF_ORG,
    CONF_PAT,
    CONF_PROJECT,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from tests.test_util.aiohttp import AiohttpClientMocker

FIXTURE_USER_INPUT = {CONF_ORG: "random", CONF_PROJECT: "project", CONF_PAT: "abc123"}


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_authorization_error(hass: HomeAssistant) -> None:
    """Test we show user form on Azure DevOps authorization error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT,
    )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "authorization_error"}


async def test_connection_error(hass: HomeAssistant) -> None:
    """Test we show user form on Azure DevOps connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.azure_devops.config_flow.DevOpsClient.authorize",
        side_effect=aiohttp.ClientError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT,
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "connection_error"}


async def test_full_flow_implementation(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test registering an integration and finishing flow works."""
    aioclient_mock.get(
        f"https://dev.azure.com/{FIXTURE_USER_INPUT[CONF_ORG]}/_apis/projects/{FIXTURE_USER_INPUT[CONF_PROJECT]}",
        json={"id": "abcd-abcd-abcd-abcd", "name": "project"},
        headers={"Content-Type": "application/json"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.azure_devops.config_flow.DevOpsClient.authorized",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT,
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert (
        result2["title"]
        == f"{FIXTURE_USER_INPUT[CONF_ORG]}/{FIXTURE_USER_INPUT[CONF_PROJECT]}"
    )
    assert result2["data"][CONF_ORG] == FIXTURE_USER_INPUT[CONF_ORG]
    assert result2["data"][CONF_PROJECT] == FIXTURE_USER_INPUT[CONF_PROJECT]
