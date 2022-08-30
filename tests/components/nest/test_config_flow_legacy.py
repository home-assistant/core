"""Tests for the Nest config flow."""
import asyncio
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.nest import DOMAIN, config_flow
from homeassistant.setup import async_setup_component

from .common import TEST_CONFIG_LEGACY

from tests.common import MockConfigEntry

CONFIG = TEST_CONFIG_LEGACY.config


async def test_abort_if_single_instance_allowed(hass):
    """Test we abort if Nest is already setup."""
    existing_entry = MockConfigEntry(domain=DOMAIN, data={})
    existing_entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, CONFIG)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_full_flow_implementation(hass):
    """Test registering an implementation and finishing flow works."""
    assert await async_setup_component(hass, DOMAIN, CONFIG)
    await hass.async_block_till_done()
    # Register an additional implementation to select from during the flow
    config_flow.register_flow_implementation(
        hass, "test-other", "Test Other", None, None
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"flow_impl": "nest"},
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "link"
    assert (
        result["description_placeholders"]
        .get("url")
        .startswith("https://home.nest.com/login/oauth2?client_id=some-client-id")
    )

    def mock_login(auth):
        assert auth.pin == "123ABC"
        auth.auth_callback({"access_token": "yoo"})

    with patch(
        "homeassistant.components.nest.legacy.local_auth.NestAuth.login", new=mock_login
    ), patch(
        "homeassistant.components.nest.async_setup_legacy_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"code": "123ABC"}
        )
        await hass.async_block_till_done()
        assert len(mock_setup.mock_calls) == 1
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["data"]["tokens"] == {"access_token": "yoo"}
        assert result["data"]["impl_domain"] == "nest"
        assert result["title"] == "Nest (via configuration.yaml)"


async def test_not_pick_implementation_if_only_one(hass):
    """Test we pick the default implementation when registered."""
    assert await async_setup_component(hass, DOMAIN, CONFIG)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "link"


async def test_abort_if_timeout_generating_auth_url(hass):
    """Test we abort if generating authorize url fails."""
    with patch(
        "homeassistant.components.nest.legacy.local_auth.generate_auth_url",
        side_effect=asyncio.TimeoutError,
    ):
        assert await async_setup_component(hass, DOMAIN, CONFIG)
        await hass.async_block_till_done()

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "authorize_url_timeout"


async def test_abort_if_exception_generating_auth_url(hass):
    """Test we abort if generating authorize url blows up."""
    with patch(
        "homeassistant.components.nest.legacy.local_auth.generate_auth_url",
        side_effect=ValueError,
    ):
        assert await async_setup_component(hass, DOMAIN, CONFIG)
        await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "unknown_authorize_url_generation"


async def test_verify_code_timeout(hass):
    """Test verify code timing out."""
    assert await async_setup_component(hass, DOMAIN, CONFIG)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "link"

    with patch(
        "homeassistant.components.nest.legacy.local_auth.NestAuth.login",
        side_effect=asyncio.TimeoutError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"code": "123ABC"}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "link"
        assert result["errors"] == {"code": "timeout"}


async def test_verify_code_invalid(hass):
    """Test verify code invalid."""
    assert await async_setup_component(hass, DOMAIN, CONFIG)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "link"

    with patch(
        "homeassistant.components.nest.legacy.local_auth.NestAuth.login",
        side_effect=config_flow.CodeInvalid,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"code": "123ABC"}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "link"
        assert result["errors"] == {"code": "invalid_pin"}


async def test_verify_code_unknown_error(hass):
    """Test verify code unknown error."""
    assert await async_setup_component(hass, DOMAIN, CONFIG)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "link"

    with patch(
        "homeassistant.components.nest.legacy.local_auth.NestAuth.login",
        side_effect=config_flow.NestAuthError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"code": "123ABC"}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "link"
        assert result["errors"] == {"code": "unknown"}


async def test_verify_code_exception(hass):
    """Test verify code blows up."""
    assert await async_setup_component(hass, DOMAIN, CONFIG)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "link"

    with patch(
        "homeassistant.components.nest.legacy.local_auth.NestAuth.login",
        side_effect=ValueError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"code": "123ABC"}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "link"
        assert result["errors"] == {"code": "internal_error"}


async def test_step_import(hass):
    """Test that we trigger import when configuring with client."""
    with patch("os.path.isfile", return_value=False):
        assert await async_setup_component(hass, DOMAIN, CONFIG)
        await hass.async_block_till_done()

    flow = hass.config_entries.flow.async_progress()[0]
    result = await hass.config_entries.flow.async_configure(flow["flow_id"])

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "link"


async def test_step_import_with_token_cache(hass):
    """Test that we import existing token cache."""
    with patch("os.path.isfile", return_value=True), patch(
        "homeassistant.components.nest.config_flow.load_json",
        return_value={"access_token": "yo"},
    ), patch(
        "homeassistant.components.nest.async_setup_legacy_entry", return_value=True
    ) as mock_setup:
        assert await async_setup_component(hass, DOMAIN, CONFIG)
        await hass.async_block_till_done()
        assert len(mock_setup.mock_calls) == 1

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.data == {"impl_domain": "nest", "tokens": {"access_token": "yo"}}
