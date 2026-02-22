"""Test the GitHub config flow."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from aiogithubapi import GitHubException
import pytest

from homeassistant.components.github.const import (
    CONF_REPOSITORIES,
    DEFAULT_REPOSITORIES,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, UnknownFlow

from .const import MOCK_ACCESS_TOKEN

from tests.common import MockConfigEntry


async def test_full_user_flow_implementation(
    hass: HomeAssistant,
    mock_setup_entry: None,
    github_device_client: AsyncMock,
    github_client: AsyncMock,
    device_activation_event: asyncio.Event,
) -> None:
    """Test the full manual user flow from start to finish."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    data_mock = MagicMock()
    data_mock.data.login = "Mock User"
    github_client.user.get = AsyncMock(return_value=data_mock)

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "device"}
    )

    assert result["step_id"] == "device"
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    device_activation_event.set()
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["step_id"] == "repositories"
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    schema = result["data_schema"]
    # SelectSelector stores options in config dict
    repositories = schema.schema[CONF_REPOSITORIES].config["options"]
    assert len(repositories) == 4

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_REPOSITORIES: DEFAULT_REPOSITORIES}
    )

    assert result["title"] == "Mock User (OAuth)"
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN}
    assert result["options"] == {CONF_REPOSITORIES: DEFAULT_REPOSITORIES}


async def test_pat_flow_implementation(
    hass: HomeAssistant,
    mock_setup_entry: None,
    github_client: AsyncMock,
) -> None:
    """Test the PAT user flow from start to finish."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    data_mock = MagicMock()
    data_mock.data.login = "Mock User"
    github_client.user.get = AsyncMock(return_value=data_mock)

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "pat"}
    )

    assert result["step_id"] == "pat"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN}
    )

    assert result["title"] == "Mock User (PAT)"
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN}
    assert result["options"] == {CONF_REPOSITORIES: []}


async def test_pat_flow_invalid_token(
    hass: HomeAssistant,
    mock_setup_entry: None,
) -> None:
    """Test the PAT user flow with invalid token."""

    client_mock = AsyncMock()

    # Ensure repos raises exception
    def raise_github_exception(*args, **kwargs):
        raise GitHubException("Invalid Token")

    client_mock.user.repos = AsyncMock()

    client_mock.user.get = AsyncMock(side_effect=raise_github_exception)

    with unittest.mock.patch(
        "homeassistant.components.github.config_flow.GitHubAPI",
        return_value=client_mock,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["step_id"] == "user"
        assert result["type"] is FlowResultType.MENU

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "pat"}
        )

        assert result["step_id"] == "pat"
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN}
        )

        assert result["step_id"] == "pat"
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_access_token"}


async def test_flow_with_registration_failure(
    hass: HomeAssistant,
    github_device_client: AsyncMock,
) -> None:
    """Test flow with registration failure of the device."""
    github_device_client.register.side_effect = GitHubException("Registration failed")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "device"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "could_not_register"


async def test_flow_with_activation_failure(
    hass: HomeAssistant,
    github_device_client: AsyncMock,
    device_activation_event: asyncio.Event,
) -> None:
    """Test flow with activation failure of the device."""

    async def mock_api_device_activation(device_code) -> None:
        # Simulate the device activation process
        await device_activation_event.wait()
        raise GitHubException("Activation failed")

    github_device_client.activation = mock_api_device_activation

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "device"}
    )

    assert result["step_id"] == "device"
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    device_activation_event.set()
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "could_not_register"


async def test_flow_with_remove_while_activating(
    hass: HomeAssistant, github_device_client: AsyncMock
) -> None:
    """Test flow with user canceling while activating."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "device"}
    )

    assert result["step_id"] == "device"
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    assert hass.config_entries.flow.async_get(result["flow_id"])

    # Simulate user canceling the flow
    hass.config_entries.flow._async_remove_flow_progress(result["flow_id"])
    await hass.async_block_till_done()

    with pytest.raises(UnknownFlow):
        hass.config_entries.flow.async_get(result["flow_id"])


async def test_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort if already configured."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, unique_id="Mock User_pat")

    # Set up the mock client to return the same username as the existing entry
    github_client = AsyncMock()
    data_mock = MagicMock()
    data_mock.data.login = "Mock User"
    github_client.user.get = AsyncMock(return_value=data_mock)

    # Patch GitHubAPI to return our mock client
    with unittest.mock.patch(
        "homeassistant.components.github.config_flow.GitHubAPI",
        return_value=github_client,
    ):
        # We need to test the PAT flow specifically as that's where the unique ID check happens
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.MENU
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "pat"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN}
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_no_repositories(
    hass: HomeAssistant,
    mock_setup_entry: None,
    github_device_client: AsyncMock,
    github_client: AsyncMock,
    device_activation_event: asyncio.Event,
) -> None:
    """Test the full manual user flow from start to finish."""

    github_client.user.repos.side_effect = [MagicMock(is_last_page=True, data=[])]
    github_client.user.starred.side_effect = [MagicMock(is_last_page=True, data=[])]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    data_mock = MagicMock()
    data_mock.data.login = "Mock User"
    github_client.user.get = AsyncMock(return_value=data_mock)

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "device"}
    )

    assert result["step_id"] == "device"
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    device_activation_event.set()
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["step_id"] == "repositories"
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    schema = result["data_schema"]
    repositories = schema.schema[CONF_REPOSITORIES].config["options"]
    assert len(repositories) == 2

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_REPOSITORIES: DEFAULT_REPOSITORIES}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Mock User (OAuth)"


async def test_exception_during_repository_fetch(
    hass: HomeAssistant,
    mock_setup_entry: None,
    github_device_client: AsyncMock,
    github_client: AsyncMock,
    device_activation_event: asyncio.Event,
) -> None:
    """Test the full manual user flow from start to finish."""

    github_client.user.repos.side_effect = GitHubException()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    data_mock = MagicMock()
    data_mock.data.login = "Mock User"
    github_client.user.get = AsyncMock(return_value=data_mock)

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "device"}
    )

    assert result["step_id"] == "device"
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    device_activation_event.set()
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["step_id"] == "repositories"
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    schema = result["data_schema"]
    repositories = schema.schema[CONF_REPOSITORIES].config["options"]
    assert len(repositories) == 2

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_REPOSITORIES: DEFAULT_REPOSITORIES}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: None,
) -> None:
    """Test options flow."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            CONF_REPOSITORIES: ["homeassistant/core", "homeassistant/architecture"]
        },
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_REPOSITORIES: ["homeassistant/core"]},
    )

    assert "homeassistant/architecture" not in result["data"][CONF_REPOSITORIES]


async def test_pat_flow_with_custom_name(
    hass: HomeAssistant,
    mock_setup_entry: None,
    github_client: AsyncMock,
) -> None:
    """Test the PAT user flow with a custom name."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    data_mock = MagicMock()
    data_mock.data.login = "Mock User"
    github_client.user.get = AsyncMock(return_value=data_mock)

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "pat"}
    )

    assert result["step_id"] == "pat"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN,
            "name": "Work",
        },
    )

    assert result["title"] == "Mock User (Work)"
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN}
    assert result["options"] == {CONF_REPOSITORIES: []}
