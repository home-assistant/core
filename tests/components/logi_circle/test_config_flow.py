"""Tests for Logi Circle config flow."""

import asyncio
from collections.abc import Generator
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.http import KEY_HASS
from homeassistant.components.logi_circle import config_flow
from homeassistant.components.logi_circle.config_flow import (
    DOMAIN,
    AuthorizationFailed,
    LogiCircleAuthCallbackView,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow, FlowResultType
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


class MockRequest:
    """Mock request passed to HomeAssistantView."""

    def __init__(self, hass: HomeAssistant, query: dict[str, Any]) -> None:
        """Init request object."""
        self.app = {KEY_HASS: hass}
        self.query = query


def init_config_flow(hass: HomeAssistant) -> config_flow.LogiCircleFlowHandler:
    """Init a configuration flow."""
    config_flow.register_flow_implementation(
        hass,
        DOMAIN,
        client_id="id",
        client_secret="secret",
        api_key="123",
        redirect_uri="http://example.com",
        sensors=None,
    )
    flow = config_flow.LogiCircleFlowHandler()
    flow._get_authorization_url = Mock(return_value="http://example.com")
    flow.hass = hass
    return flow


@pytest.fixture
def mock_logi_circle() -> Generator[MagicMock]:
    """Mock logi_circle."""
    with patch(
        "homeassistant.components.logi_circle.config_flow.LogiCircle"
    ) as logi_circle:
        future = asyncio.Future()
        future.set_result({"accountId": "testId"})
        LogiCircle = logi_circle()
        LogiCircle.authorize = AsyncMock(return_value=True)
        LogiCircle.close = AsyncMock(return_value=True)
        LogiCircle.account = future
        LogiCircle.authorize_url = "http://authorize.url"
        yield LogiCircle


@pytest.mark.usefixtures("mock_logi_circle")
async def test_step_import(hass: HomeAssistant) -> None:
    """Test that we trigger import when configuring with client."""
    flow = init_config_flow(hass)

    result = await flow.async_step_import()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"


@pytest.mark.usefixtures("mock_logi_circle")
async def test_full_flow_implementation(hass: HomeAssistant) -> None:
    """Test registering an implementation and finishing flow works."""
    config_flow.register_flow_implementation(
        hass,
        "test-other",
        client_id=None,
        client_secret=None,
        api_key=None,
        redirect_uri=None,
        sensors=None,
    )
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await flow.async_step_user({"flow_impl": "test-other"})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["description_placeholders"] == {
        "authorization_url": "http://example.com"
    }

    result = await flow.async_step_code("123ABC")
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Logi Circle ({})".format("testId")


async def test_we_reprompt_user_to_follow_link(hass: HomeAssistant) -> None:
    """Test we prompt user to follow link if previously prompted."""
    flow = init_config_flow(hass)

    result = await flow.async_step_auth("dummy")
    assert result["errors"]["base"] == "follow_link"


async def test_abort_if_no_implementation_registered(hass: HomeAssistant) -> None:
    """Test we abort if no implementation is registered."""
    flow = config_flow.LogiCircleFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_configuration"


async def test_abort_if_already_setup(hass: HomeAssistant) -> None:
    """Test we abort if Logi Circle is already setup."""
    flow = init_config_flow(hass)
    MockConfigEntry(domain=config_flow.DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    with pytest.raises(AbortFlow):
        result = await flow.async_step_code()

    result = await flow.async_step_auth()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "external_setup"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (TimeoutError, "authorize_url_timeout"),
        (AuthorizationFailed, "invalid_auth"),
    ],
)
async def test_abort_if_authorize_fails(
    hass: HomeAssistant,
    mock_logi_circle: MagicMock,
    side_effect: type[Exception],
    error: str,
) -> None:
    """Test we abort if authorizing fails."""
    flow = init_config_flow(hass)
    mock_logi_circle.authorize.side_effect = side_effect

    result = await flow.async_step_code("123ABC")
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "external_error"

    result = await flow.async_step_auth()
    assert result["errors"]["base"] == error


async def test_not_pick_implementation_if_only_one(hass: HomeAssistant) -> None:
    """Test we bypass picking implementation if we have one flow_imp."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"


@pytest.mark.usefixtures("mock_logi_circle")
async def test_gen_auth_url(hass: HomeAssistant) -> None:
    """Test generating authorize URL from Logi Circle API."""
    config_flow.register_flow_implementation(
        hass,
        "test-auth-url",
        client_id="id",
        client_secret="secret",
        api_key="123",
        redirect_uri="http://example.com",
        sensors=None,
    )
    flow = config_flow.LogiCircleFlowHandler()
    flow.hass = hass
    flow.flow_impl = "test-auth-url"
    await async_setup_component(hass, "http", {})

    result = flow._get_authorization_url()
    assert result == "http://authorize.url"


async def test_callback_view_rejects_missing_code(hass: HomeAssistant) -> None:
    """Test the auth callback view rejects requests with no code."""
    view = LogiCircleAuthCallbackView()
    resp = await view.get(MockRequest(hass, {}))

    assert resp.status == HTTPStatus.BAD_REQUEST


async def test_callback_view_accepts_code(
    hass: HomeAssistant, mock_logi_circle: MagicMock
) -> None:
    """Test the auth callback view handles requests with auth code."""
    init_config_flow(hass)
    view = LogiCircleAuthCallbackView()

    resp = await view.get(MockRequest(hass, {"code": "456"}))
    assert resp.status == HTTPStatus.OK

    await hass.async_block_till_done()
    mock_logi_circle.authorize.assert_called_with("456")
