"""Test the GitHub config flow."""

import asyncio
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

    assert result["step_id"] == "device"
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    device_activation_event.set()
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["step_id"] == "repositories"
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    schema = result["data_schema"]
    repositories = schema.schema[CONF_REPOSITORIES].options
    assert len(repositories) == 4

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_REPOSITORIES: DEFAULT_REPOSITORIES}
    )

    assert result["title"] == ""
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN}
    assert result["options"] == {CONF_REPOSITORIES: DEFAULT_REPOSITORIES}


async def test_flow_with_registration_failure(
    hass: HomeAssistant,
    github_device_client: AsyncMock,
) -> None:
    """Test flow with registration failure of the device."""
    github_device_client.register.side_effect = GitHubException("Registration failed")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
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

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
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

    assert result["step_id"] == "device"
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    device_activation_event.set()
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["step_id"] == "repositories"
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    schema = result["data_schema"]
    repositories = schema.schema[CONF_REPOSITORIES].options
    assert len(repositories) == 2

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_REPOSITORIES: DEFAULT_REPOSITORIES}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


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

    assert result["step_id"] == "device"
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    device_activation_event.set()
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["step_id"] == "repositories"
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    schema = result["data_schema"]
    repositories = schema.schema[CONF_REPOSITORIES].options
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
