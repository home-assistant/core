"""Tests for the Point config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.point import DOMAIN, config_flow
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


def init_config_flow(hass, side_effect=None):
    """Init a configuration flow."""
    config_flow.register_flow_implementation(hass, DOMAIN, "id", "secret")
    flow = config_flow.PointFlowHandler()
    flow._get_authorization_url = AsyncMock(
        return_value="https://example.com", side_effect=side_effect
    )
    flow.hass = hass
    return flow


@pytest.fixture
def is_authorized():
    """Set PointSession authorized."""
    return True


@pytest.fixture
def mock_pypoint(is_authorized):
    """Mock pypoint."""
    with patch(
        "homeassistant.components.point.config_flow.PointSession"
    ) as PointSession:
        PointSession.return_value.get_access_token = AsyncMock(
            return_value={"access_token": "boo"}
        )
        PointSession.return_value.is_authorized = is_authorized
        PointSession.return_value.user = AsyncMock(
            return_value={"email": "john.doe@example.com"}
        )
        yield PointSession


async def test_abort_if_no_implementation_registered(hass: HomeAssistant) -> None:
    """Test we abort if no implementation is registered."""
    flow = config_flow.PointFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_flows"


async def test_abort_if_already_setup(hass: HomeAssistant) -> None:
    """Test we abort if Point is already setup."""
    flow = init_config_flow(hass)

    with patch.object(hass.config_entries, "async_entries", return_value=[{}]):
        result = await flow.async_step_user()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_setup"

    with patch.object(hass.config_entries, "async_entries", return_value=[{}]):
        result = await flow.async_step_import()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_setup"


async def test_full_flow_implementation(hass: HomeAssistant, mock_pypoint) -> None:
    """Test registering an implementation and finishing flow works."""
    config_flow.register_flow_implementation(hass, "test-other", None, None)
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await flow.async_step_user({"flow_impl": "test"})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["description_placeholders"] == {
        "authorization_url": "https://example.com"
    }

    result = await flow.async_step_code("123ABC")
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["refresh_args"] == {
        CONF_CLIENT_ID: "id",
        CONF_CLIENT_SECRET: "secret",
    }
    assert result["title"] == "john.doe@example.com"
    assert result["data"]["token"] == {"access_token": "boo"}


async def test_step_import(hass: HomeAssistant, mock_pypoint) -> None:
    """Test that we trigger import when configuring with client."""
    flow = init_config_flow(hass)

    result = await flow.async_step_import()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"


@pytest.mark.parametrize("is_authorized", [False])
async def test_wrong_code_flow_implementation(
    hass: HomeAssistant, mock_pypoint
) -> None:
    """Test wrong code."""
    flow = init_config_flow(hass)

    result = await flow.async_step_code("123ABC")
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "auth_error"


async def test_not_pick_implementation_if_only_one(hass: HomeAssistant) -> None:
    """Test we allow picking implementation if we have one flow_imp."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"


async def test_abort_if_timeout_generating_auth_url(hass: HomeAssistant) -> None:
    """Test we abort if generating authorize url fails."""
    flow = init_config_flow(hass, side_effect=TimeoutError)

    result = await flow.async_step_user()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "authorize_url_timeout"


async def test_abort_if_exception_generating_auth_url(hass: HomeAssistant) -> None:
    """Test we abort if generating authorize url blows up."""
    flow = init_config_flow(hass, side_effect=ValueError)

    result = await flow.async_step_user()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown_authorize_url_generation"


async def test_abort_no_code(hass: HomeAssistant) -> None:
    """Test if no code is given to step_code."""
    flow = init_config_flow(hass)

    result = await flow.async_step_code()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_code"
