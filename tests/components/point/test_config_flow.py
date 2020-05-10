"""Tests for the Point config flow."""
import asyncio

import pytest

from homeassistant import data_entry_flow
from homeassistant.components.point import DOMAIN, config_flow

from tests.async_mock import AsyncMock, patch


def init_config_flow(hass, side_effect=None):
    """Init a configuration flow."""
    config_flow.register_flow_implementation(hass, DOMAIN, "id", "secret")
    flow = config_flow.PointFlowHandler()
    flow._get_authorization_url = AsyncMock(  # pylint: disable=protected-access
        return_value="https://example.com", side_effect=side_effect
    )
    flow.hass = hass
    return flow


@pytest.fixture
def is_authorized():
    """Set PointSession authorized."""
    return True


@pytest.fixture
def mock_pypoint(is_authorized):  # pylint: disable=redefined-outer-name
    """Mock pypoint."""
    with patch(
        "homeassistant.components.point.config_flow.PointSession"
    ) as PointSession:
        PointSession.return_value.get_access_token.return_value = {
            "access_token": "boo"
        }
        PointSession.return_value.is_authorized = is_authorized
        PointSession.return_value.user.return_value = {"email": "john.doe@example.com"}
        yield PointSession


async def test_abort_if_no_implementation_registered(hass):
    """Test we abort if no implementation is registered."""
    flow = config_flow.PointFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "no_flows"


async def test_abort_if_already_setup(hass):
    """Test we abort if Point is already setup."""
    flow = init_config_flow(hass)

    with patch.object(hass.config_entries, "async_entries", return_value=[{}]):
        result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_setup"

    with patch.object(hass.config_entries, "async_entries", return_value=[{}]):
        result = await flow.async_step_import()
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_setup"


async def test_full_flow_implementation(
    hass, mock_pypoint  # pylint: disable=redefined-outer-name
):
    """Test registering an implementation and finishing flow works."""
    config_flow.register_flow_implementation(hass, "test-other", None, None)
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await flow.async_step_user({"flow_impl": "test"})
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "auth"
    assert result["description_placeholders"] == {
        "authorization_url": "https://example.com"
    }

    result = await flow.async_step_code("123ABC")
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"]["refresh_args"] == {
        "client_id": "id",
        "client_secret": "secret",
    }
    assert result["title"] == "john.doe@example.com"
    assert result["data"]["token"] == {"access_token": "boo"}


async def test_step_import(hass, mock_pypoint):  # pylint: disable=redefined-outer-name
    """Test that we trigger import when configuring with client."""
    flow = init_config_flow(hass)

    result = await flow.async_step_import()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "auth"


@pytest.mark.parametrize("is_authorized", [False])
async def test_wrong_code_flow_implementation(
    hass, mock_pypoint
):  # pylint: disable=redefined-outer-name
    """Test wrong code."""
    flow = init_config_flow(hass)

    result = await flow.async_step_code("123ABC")
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "auth_error"


async def test_not_pick_implementation_if_only_one(hass):
    """Test we allow picking implementation if we have one flow_imp."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "auth"


async def test_abort_if_timeout_generating_auth_url(hass):
    """Test we abort if generating authorize url fails."""
    flow = init_config_flow(hass, side_effect=asyncio.TimeoutError)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "authorize_url_timeout"


async def test_abort_if_exception_generating_auth_url(hass):
    """Test we abort if generating authorize url blows up."""
    flow = init_config_flow(hass, side_effect=ValueError)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "authorize_url_fail"


async def test_abort_no_code(hass):
    """Test if no code is given to step_code."""
    flow = init_config_flow(hass)

    result = await flow.async_step_code()
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "no_code"
