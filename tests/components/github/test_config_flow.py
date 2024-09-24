"""Test the GitHub config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from aiogithubapi import GitHubException
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant import config_entries
from homeassistant.components.github.config_flow import get_repositories
from homeassistant.components.github.const import (
    CONF_REPOSITORIES,
    DEFAULT_REPOSITORIES,
    DOMAIN,
)
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, UnknownFlow

from .common import MOCK_ACCESS_TOKEN

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_full_user_flow_implementation(
    hass: HomeAssistant,
    mock_setup_entry: None,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the full manual user flow from start to finish."""
    aioclient_mock.post(
        "https://github.com/login/device/code",
        json={
            "device_code": "3584d83530557fdd1f46af8289938c8ef79f9dc5",
            "user_code": "WDJB-MJHT",
            "verification_uri": "https://github.com/login/device",
            "expires_in": 900,
            "interval": 5,
        },
        headers={"Content-Type": "application/json"},
    )
    # User has not yet entered the code
    aioclient_mock.post(
        "https://github.com/login/oauth/access_token",
        json={"error": "authorization_pending"},
        headers={"Content-Type": "application/json"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["step_id"] == "device"
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    # User enters the code
    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://github.com/login/oauth/access_token",
        json={
            CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN,
            "token_type": "bearer",
            "scope": "",
        },
        headers={"Content-Type": "application/json"},
    )
    freezer.tick(10)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_REPOSITORIES: DEFAULT_REPOSITORIES,
        },
    )

    assert result["title"] == ""
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "data" in result
    assert result["data"][CONF_ACCESS_TOKEN] == MOCK_ACCESS_TOKEN
    assert "options" in result
    assert result["options"][CONF_REPOSITORIES] == DEFAULT_REPOSITORIES


async def test_flow_with_registration_failure(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test flow with registration failure of the device."""
    aioclient_mock.post(
        "https://github.com/login/device/code",
        exc=GitHubException("Registration failed"),
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result.get("reason") == "could_not_register"


async def test_flow_with_activation_failure(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test flow with activation failure of the device."""
    aioclient_mock.post(
        "https://github.com/login/device/code",
        json={
            "device_code": "3584d83530557fdd1f46af8289938c8ef79f9dc5",
            "user_code": "WDJB-MJHT",
            "verification_uri": "https://github.com/login/device",
            "expires_in": 900,
            "interval": 5,
        },
        headers={"Content-Type": "application/json"},
    )
    # User has not yet entered the code
    aioclient_mock.post(
        "https://github.com/login/oauth/access_token",
        json={"error": "authorization_pending"},
        headers={"Content-Type": "application/json"},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["step_id"] == "device"
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    # Activation fails
    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://github.com/login/oauth/access_token",
        exc=GitHubException("Activation failed"),
    )
    freezer.tick(10)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "could_not_register"


async def test_flow_with_remove_while_activating(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test flow with user canceling while activating."""
    aioclient_mock.post(
        "https://github.com/login/device/code",
        json={
            "device_code": "3584d83530557fdd1f46af8289938c8ef79f9dc5",
            "user_code": "WDJB-MJHT",
            "verification_uri": "https://github.com/login/device",
            "expires_in": 900,
            "interval": 5,
        },
        headers={"Content-Type": "application/json"},
    )
    aioclient_mock.post(
        "https://github.com/login/oauth/access_token",
        json={"error": "authorization_pending"},
        headers={"Content-Type": "application/json"},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
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
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_starred_pagination_with_paginated_result(hass: HomeAssistant) -> None:
    """Test pagination of starred repositories with paginated result."""
    with patch(
        "homeassistant.components.github.config_flow.GitHubAPI",
        return_value=MagicMock(
            user=MagicMock(
                starred=AsyncMock(
                    return_value=MagicMock(
                        is_last_page=False,
                        next_page_number=2,
                        last_page_number=2,
                        data=[MagicMock(full_name="home-assistant/core")],
                    )
                ),
                repos=AsyncMock(
                    return_value=MagicMock(
                        is_last_page=False,
                        next_page_number=2,
                        last_page_number=2,
                        data=[MagicMock(full_name="awesome/reposiotry")],
                    )
                ),
            )
        ),
    ):
        repos = await get_repositories(hass, MOCK_ACCESS_TOKEN)

    assert len(repos) == 2
    assert repos[-1] == DEFAULT_REPOSITORIES[0]


async def test_starred_pagination_with_no_starred(hass: HomeAssistant) -> None:
    """Test pagination of starred repositories with no starred."""
    with patch(
        "homeassistant.components.github.config_flow.GitHubAPI",
        return_value=MagicMock(
            user=MagicMock(
                starred=AsyncMock(
                    return_value=MagicMock(
                        is_last_page=True,
                        data=[],
                    )
                ),
                repos=AsyncMock(
                    return_value=MagicMock(
                        is_last_page=True,
                        data=[],
                    )
                ),
            )
        ),
    ):
        repos = await get_repositories(hass, MOCK_ACCESS_TOKEN)

    assert len(repos) == 2
    assert repos == DEFAULT_REPOSITORIES


async def test_starred_pagination_with_exception(hass: HomeAssistant) -> None:
    """Test pagination of starred repositories with exception."""
    with patch(
        "homeassistant.components.github.config_flow.GitHubAPI",
        return_value=MagicMock(
            user=MagicMock(starred=AsyncMock(side_effect=GitHubException("Error")))
        ),
    ):
        repos = await get_repositories(hass, MOCK_ACCESS_TOKEN)

    assert len(repos) == 2
    assert repos == DEFAULT_REPOSITORIES


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
