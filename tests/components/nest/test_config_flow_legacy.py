"""Tests for the Nest config flow."""
import asyncio
from unittest.mock import Mock, patch

from homeassistant import data_entry_flow
from homeassistant.components.nest import DOMAIN, config_flow
from homeassistant.setup import async_setup_component

from tests.async_mock import AsyncMock
from tests.common import mock_coro


async def test_abort_if_no_implementation_registered(hass):
    """Test we abort if no implementation is registered."""
    flow = config_flow.NestFlowHandler()
    flow.hass = hass
    result = await flow.async_step_init()

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "missing_configuration"


async def test_abort_if_single_instance_allowed(hass):
    """Test we abort if Nest is already setup."""
    flow = config_flow.NestFlowHandler()
    flow.hass = hass

    with patch.object(hass.config_entries, "async_entries", return_value=[{}]):
        result = await flow.async_step_init()

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_full_flow_implementation(hass):
    """Test registering an implementation and finishing flow works."""
    gen_authorize_url = AsyncMock(return_value="https://example.com")
    convert_code = AsyncMock(return_value={"access_token": "yoo"})
    config_flow.register_flow_implementation(
        hass, "test", "Test", gen_authorize_url, convert_code
    )
    config_flow.register_flow_implementation(
        hass, "test-other", "Test Other", None, None
    )

    flow = config_flow.NestFlowHandler()
    flow.hass = hass
    result = await flow.async_step_init()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await flow.async_step_init({"flow_impl": "test"})
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "link"
    assert result["description_placeholders"] == {"url": "https://example.com"}

    result = await flow.async_step_link({"code": "123ABC"})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"]["tokens"] == {"access_token": "yoo"}
    assert result["data"]["impl_domain"] == "test"
    assert result["title"] == "Nest (via Test)"


async def test_not_pick_implementation_if_only_one(hass):
    """Test we allow picking implementation if we have two."""
    gen_authorize_url = AsyncMock(return_value="https://example.com")
    config_flow.register_flow_implementation(
        hass, "test", "Test", gen_authorize_url, None
    )

    flow = config_flow.NestFlowHandler()
    flow.hass = hass
    result = await flow.async_step_init()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "link"


async def test_abort_if_timeout_generating_auth_url(hass):
    """Test we abort if generating authorize url fails."""
    gen_authorize_url = Mock(side_effect=asyncio.TimeoutError)
    config_flow.register_flow_implementation(
        hass, "test", "Test", gen_authorize_url, None
    )

    flow = config_flow.NestFlowHandler()
    flow.hass = hass
    result = await flow.async_step_init()
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "authorize_url_timeout"


async def test_abort_if_exception_generating_auth_url(hass):
    """Test we abort if generating authorize url blows up."""
    gen_authorize_url = Mock(side_effect=ValueError)
    config_flow.register_flow_implementation(
        hass, "test", "Test", gen_authorize_url, None
    )

    flow = config_flow.NestFlowHandler()
    flow.hass = hass
    result = await flow.async_step_init()
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "unknown_authorize_url_generation"


async def test_verify_code_timeout(hass):
    """Test verify code timing out."""
    gen_authorize_url = AsyncMock(return_value="https://example.com")
    convert_code = Mock(side_effect=asyncio.TimeoutError)
    config_flow.register_flow_implementation(
        hass, "test", "Test", gen_authorize_url, convert_code
    )

    flow = config_flow.NestFlowHandler()
    flow.hass = hass
    result = await flow.async_step_init()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "link"

    result = await flow.async_step_link({"code": "123ABC"})
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "link"
    assert result["errors"] == {"code": "timeout"}


async def test_verify_code_invalid(hass):
    """Test verify code invalid."""
    gen_authorize_url = AsyncMock(return_value="https://example.com")
    convert_code = Mock(side_effect=config_flow.CodeInvalid)
    config_flow.register_flow_implementation(
        hass, "test", "Test", gen_authorize_url, convert_code
    )

    flow = config_flow.NestFlowHandler()
    flow.hass = hass
    result = await flow.async_step_init()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "link"

    result = await flow.async_step_link({"code": "123ABC"})
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "link"
    assert result["errors"] == {"code": "invalid_pin"}


async def test_verify_code_unknown_error(hass):
    """Test verify code unknown error."""
    gen_authorize_url = AsyncMock(return_value="https://example.com")
    convert_code = Mock(side_effect=config_flow.NestAuthError)
    config_flow.register_flow_implementation(
        hass, "test", "Test", gen_authorize_url, convert_code
    )

    flow = config_flow.NestFlowHandler()
    flow.hass = hass
    result = await flow.async_step_init()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "link"

    result = await flow.async_step_link({"code": "123ABC"})
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "link"
    assert result["errors"] == {"code": "unknown"}


async def test_verify_code_exception(hass):
    """Test verify code blows up."""
    gen_authorize_url = AsyncMock(return_value="https://example.com")
    convert_code = Mock(side_effect=ValueError)
    config_flow.register_flow_implementation(
        hass, "test", "Test", gen_authorize_url, convert_code
    )

    flow = config_flow.NestFlowHandler()
    flow.hass = hass
    result = await flow.async_step_init()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "link"

    result = await flow.async_step_link({"code": "123ABC"})
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "link"
    assert result["errors"] == {"code": "internal_error"}


async def test_step_import(hass):
    """Test that we trigger import when configuring with client."""
    with patch("os.path.isfile", return_value=False):
        assert await async_setup_component(
            hass, DOMAIN, {DOMAIN: {"client_id": "bla", "client_secret": "bla"}}
        )
        await hass.async_block_till_done()

    flow = hass.config_entries.flow.async_progress()[0]
    result = await hass.config_entries.flow.async_configure(flow["flow_id"])

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "link"


async def test_step_import_with_token_cache(hass):
    """Test that we import existing token cache."""
    with patch("os.path.isfile", return_value=True), patch(
        "homeassistant.components.nest.config_flow.load_json",
        return_value={"access_token": "yo"},
    ), patch(
        "homeassistant.components.nest.async_setup_entry", return_value=mock_coro(True)
    ):
        assert await async_setup_component(
            hass, DOMAIN, {DOMAIN: {"client_id": "bla", "client_secret": "bla"}}
        )
        await hass.async_block_till_done()

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.data == {"impl_domain": "nest", "tokens": {"access_token": "yo"}}
