"""Test Lidarr config flow."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest

from homeassistant.components.lidarr.const import DEFAULT_NAME, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_SOURCE, CONTENT_TYPE_JSON
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import API_URL, CONF_DATA, MOCK_INPUT, URL, ComponentSetup

from tests.common import MockConfigEntry, async_load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


@asynccontextmanager
async def _patch_connection(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> AsyncGenerator[None]:
    """Mock a working Lidarr connection and skip entry setup."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        f"{URL}/initialize.js",
        text=await async_load_fixture(hass, "initialize.js", DOMAIN),
        headers={"Content-Type": "application/javascript"},
    )
    aioclient_mock.get(
        f"{API_URL}/system/status",
        text=await async_load_fixture(hass, "system-status.json", DOMAIN),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )
    with patch("homeassistant.components.lidarr.async_setup_entry", return_value=True):
        yield


async def test_flow_user_form(hass: HomeAssistant, connection) -> None:
    """Test that the user set up form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_INPUT,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == CONF_DATA


@pytest.mark.usefixtures("invalid_auth")
async def test_flow_user_invalid_auth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test invalid authentication."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=CONF_DATA,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "invalid_auth"

    async with _patch_connection(hass, aioclient_mock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_DATA,
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("cannot_connect")
async def test_flow_user_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=CONF_DATA,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "cannot_connect"

    async with _patch_connection(hass, aioclient_mock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_DATA,
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("wrong_app")
async def test_wrong_app(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we show user form on wrong app."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=MOCK_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "wrong_app"

    async with _patch_connection(hass, aioclient_mock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_INPUT,
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("zeroconf_failed")
async def test_zeroconf_failed(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we show user form on zeroconf failure."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=MOCK_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "zeroconf_failed"

    async with _patch_connection(hass, aioclient_mock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_INPUT,
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("unknown")
async def test_flow_user_unknown_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_DATA,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "unknown"

    async with _patch_connection(hass, aioclient_mock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_DATA,
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_flow_reauth(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    connection,
    config_entry: MockConfigEntry,
) -> None:
    """Test reauth."""
    await setup_integration()
    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: "abc123"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_API_KEY] == "abc123"
