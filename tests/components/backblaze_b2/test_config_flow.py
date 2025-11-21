"""Backblaze B2 config flow tests."""

from unittest.mock import patch

from b2sdk.v2 import exception
import pytest

from homeassistant.components.backblaze_b2.const import (
    CONF_APPLICATION_KEY,
    CONF_KEY_ID,
    DOMAIN,
)
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    ConfigFlowResult,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import BackblazeFixture
from .const import USER_INPUT

from tests.common import MockConfigEntry


async def _async_start_flow(
    hass: HomeAssistant,
    key_id: str,
    application_key: str,
    user_input: dict[str, str] | None = None,
) -> ConfigFlowResult:
    """Initialize the config flow."""
    if user_input is None:
        user_input = USER_INPUT

    user_input[CONF_KEY_ID] = key_id
    user_input[CONF_APPLICATION_KEY] = application_key
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {}

    return await hass.config_entries.flow.async_configure(result["flow_id"], user_input)


async def test_basic_flows(hass: HomeAssistant, b2_fixture: BackblazeFixture) -> None:
    """Test basic successful config flows."""
    result = await _async_start_flow(
        hass, b2_fixture.key_id, b2_fixture.application_key
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "testBucket"
    assert result.get("data") == USER_INPUT


async def test_prefix_normalization(
    hass: HomeAssistant, b2_fixture: BackblazeFixture
) -> None:
    """Test prefix normalization in config flow."""
    user_input = {**USER_INPUT, "prefix": "test-prefix/foo"}
    result = await _async_start_flow(
        hass, b2_fixture.key_id, b2_fixture.application_key, user_input
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result["data"]["prefix"] == "test-prefix/foo/"


async def test_empty_prefix(hass: HomeAssistant, b2_fixture: BackblazeFixture) -> None:
    """Test empty prefix handling."""
    user_input_empty = {**USER_INPUT, "prefix": ""}
    result = await _async_start_flow(
        hass, b2_fixture.key_id, b2_fixture.application_key, user_input_empty
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result["data"]["prefix"] == ""


async def test_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    b2_fixture: BackblazeFixture,
) -> None:
    """Test abort if already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await _async_start_flow(
        hass, b2_fixture.key_id, b2_fixture.application_key
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


@pytest.mark.parametrize(
    ("error_type", "setup", "expected_error", "expected_field"),
    [
        (
            "invalid_auth",
            {"key_id": "invalid", "app_key": "invalid"},
            "invalid_credentials",
            "base",
        ),
        (
            "invalid_bucket",
            {"bucket": "invalid-bucket-name"},
            "invalid_bucket_name",
            "bucket",
        ),
        (
            "cannot_connect",
            {
                "patch": "b2sdk.v2.RawSimulator.authorize_account",
                "exception": exception.ConnectionReset,
                "args": ["test"],
            },
            "cannot_connect",
            "base",
        ),
        (
            "restricted_bucket",
            {
                "patch": "b2sdk.v2.RawSimulator.get_bucket_by_name",
                "exception": exception.RestrictedBucket,
                "args": ["testBucket"],
            },
            "restricted_bucket",
            "bucket",
        ),
        (
            "missing_account_data",
            {
                "patch": "b2sdk.v2.RawSimulator.authorize_account",
                "exception": exception.MissingAccountData,
                "args": ["key"],
            },
            "invalid_credentials",
            "base",
        ),
        (
            "invalid_capability",
            {"mock_capabilities": ["writeFiles", "listFiles", "deleteFiles"]},
            "invalid_capability",
            "base",
        ),
        (
            "no_allowed_info",
            {"mock_allowed": None},
            "invalid_capability",
            "base",
        ),
        (
            "no_capabilities",
            {"mock_allowed": {}},
            "invalid_capability",
            "base",
        ),
        ("invalid_prefix", {"mock_prefix": "test/"}, "invalid_prefix", "prefix"),
        (
            "unknown_error",
            {
                "patch": "b2sdk.v2.RawSimulator.authorize_account",
                "exception": RuntimeError,
                "args": ["Unexpected error"],
            },
            "unknown",
            "base",
        ),
    ],
)
async def test_config_flow_errors(
    hass: HomeAssistant,
    b2_fixture: BackblazeFixture,
    error_type: str,
    setup: dict,
    expected_error: str,
    expected_field: str,
) -> None:
    """Test various config flow error scenarios."""

    if error_type == "invalid_auth":
        result = await _async_start_flow(hass, setup["key_id"], setup["app_key"])
    elif error_type == "invalid_bucket":
        invalid_input = {**USER_INPUT, "bucket": setup["bucket"]}
        result = await _async_start_flow(
            hass, b2_fixture.key_id, b2_fixture.application_key, invalid_input
        )
    elif "patch" in setup:
        with patch(setup["patch"], side_effect=setup["exception"](*setup["args"])):
            result = await _async_start_flow(
                hass, b2_fixture.key_id, b2_fixture.application_key
            )
    elif "mock_capabilities" in setup:
        with patch(
            "b2sdk.v2.RawSimulator.account_info.get_allowed",
            return_value={"capabilities": setup["mock_capabilities"]},
        ):
            result = await _async_start_flow(
                hass, b2_fixture.key_id, b2_fixture.application_key
            )
    elif "mock_allowed" in setup:
        with patch(
            "b2sdk.v2.RawSimulator.account_info.get_allowed",
            return_value=setup["mock_allowed"],
        ):
            result = await _async_start_flow(
                hass, b2_fixture.key_id, b2_fixture.application_key
            )
    elif "mock_prefix" in setup:
        with patch(
            "b2sdk.v2.RawSimulator.account_info.get_allowed",
            return_value={
                "capabilities": ["writeFiles", "listFiles", "deleteFiles", "readFiles"],
                "namePrefix": setup["mock_prefix"],
            },
        ):
            result = await _async_start_flow(
                hass, b2_fixture.key_id, b2_fixture.application_key
            )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {expected_field: expected_error}

    if error_type == "restricted_bucket":
        assert result.get("description_placeholders") == {
            "brand_name": "Backblaze B2",
            "restricted_bucket_name": "testBucket",
        }
    elif error_type == "invalid_prefix":
        assert result.get("description_placeholders") == {
            "brand_name": "Backblaze B2",
            "allowed_prefix": "test/",
        }


@pytest.mark.parametrize(
    ("flow_type", "scenario"),
    [
        ("reauth", "success"),
        ("reauth", "invalid_credentials"),
        ("reconfigure", "success"),
        ("reconfigure", "prefix_normalization"),
        ("reconfigure", "validation_error"),
    ],
)
async def test_advanced_flows(
    hass: HomeAssistant,
    b2_fixture: BackblazeFixture,
    mock_config_entry: MockConfigEntry,
    flow_type: str,
    scenario: str,
) -> None:
    """Test reauthentication and reconfiguration flows."""
    mock_config_entry.add_to_hass(hass)

    if flow_type == "reauth":
        source = SOURCE_REAUTH
        step_name = "reauth_confirm"

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": source, "entry_id": mock_config_entry.entry_id},
        )
        assert result.get("type") is FlowResultType.FORM
        assert result.get("step_id") == step_name

        if scenario == "success":
            config = {
                CONF_KEY_ID: b2_fixture.key_id,
                CONF_APPLICATION_KEY: b2_fixture.application_key,
            }
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], config
            )
            assert result.get("type") is FlowResultType.ABORT
            assert result.get("reason") == "reauth_successful"

        else:  # invalid_credentials
            config = {CONF_KEY_ID: "invalid", CONF_APPLICATION_KEY: "invalid"}
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], config
            )
            assert result.get("type") is FlowResultType.FORM
            assert result.get("errors") == {"base": "invalid_credentials"}

    elif flow_type == "reconfigure":
        source = SOURCE_RECONFIGURE
        step_name = "reconfigure"

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": source, "entry_id": mock_config_entry.entry_id},
        )
        assert result.get("type") is FlowResultType.FORM
        assert result.get("step_id") == step_name

        if scenario == "success":
            config = {
                CONF_KEY_ID: b2_fixture.key_id,
                CONF_APPLICATION_KEY: b2_fixture.application_key,
                "bucket": "testBucket",
                "prefix": "new_prefix/",
            }
        elif scenario == "prefix_normalization":
            config = {
                CONF_KEY_ID: b2_fixture.key_id,
                CONF_APPLICATION_KEY: b2_fixture.application_key,
                "bucket": "testBucket",
                "prefix": "no_slash_prefix",
            }
        else:  # validation_error
            config = {
                CONF_KEY_ID: "invalid_key",
                CONF_APPLICATION_KEY: "invalid_app_key",
                "bucket": "invalid_bucket",
                "prefix": "",
            }

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], config
        )

        if scenario == "validation_error":
            assert result.get("type") is FlowResultType.FORM
            assert result.get("errors") == {"base": "invalid_credentials"}
        else:
            assert result.get("type") is FlowResultType.ABORT
            assert result.get("reason") == "reconfigure_successful"
