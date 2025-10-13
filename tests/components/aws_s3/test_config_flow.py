"""Test the AWS S3 config flow."""

from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.aws_s3.config_flow import S3ConfigFlow
from homeassistant.components.aws_s3.config_model import S3ConfigModel
from homeassistant.components.aws_s3.const import (
    CONF_ACCESS_KEY_ID,
    CONF_AUTH_MODE,
    CONF_BUCKET,
    CONF_ENDPOINT_URL,
    CONF_PROFILE_NAME,
    CONF_SECRET_ACCESS_KEY,
    DEFAULT_ENDPOINT_URL,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.selector import TextSelectorType

from .const import (
    TEST_ENDPOINT_URL,
    TEST_INVALID,
    USER_INPUT_VALID_EXPLICIT,
    USER_INPUT_VALID_IMPLICIT,
    USER_INPUT_VALID_PROFILE,
)

from tests.common import ConfigFlowResult, MockConfigEntry

####################
# HELPER FUNCTIONS
####################


def _validate_data_schema_output(
    data_schema: vol.Schema,
    expected_keys: set[str],
    expected_readonly: set[str],
    expected_types: dict[str, str],
    expected_values: dict[str, str],
) -> None:
    """Validate an outputted data schema against expected keys, types, and values."""
    schema_detail = {
        k.schema: (k, data_schema.schema[k].config) for k in data_schema.schema
    }

    assert schema_detail.keys() == expected_keys

    for k in expected_readonly:
        assert schema_detail[k][1].get("read_only")

    for k in expected_keys - expected_readonly:
        assert not schema_detail[k][1].get("read_only")

    for k, v in expected_values.items():
        suggested_value = (
            schema_detail[k][0].description.get("suggested_value")
            if schema_detail[k][0].description
            else None
        )
        default_value = (
            schema_detail[k][0].default()
            if not isinstance(schema_detail[k][0].default, vol.Undefined)
            else None
        )
        assert (suggested_value or default_value) == v

    for k in expected_keys - expected_values.keys():
        suggested_value = (
            schema_detail[k][0].description.get("suggested_value")
            if schema_detail[k][0].description
            else None
        )
        default_value = (
            schema_detail[k][0].default()
            if not isinstance(schema_detail[k][0].default, vol.Undefined)
            else None
        )
        assert not (suggested_value and default_value)

    for k, v in expected_types.items():
        assert schema_detail[k][1]["type"] == v


def _record_errors(model: S3ConfigModel, errors: dict[str, str]) -> None:
    """Record errors in the S3ConfigModel instance."""
    for k, v in errors.items():
        model.record_error(k, v)


#####################
# GENERIC FLOW TESTS
#####################


@pytest.mark.parametrize(
    ("context"),
    [
        config_entries.ConfigFlowContext(source=config_entries.SOURCE_USER),
        config_entries.ConfigFlowContext(
            source=config_entries.SOURCE_REAUTH, entry_id="Test"
        ),
        config_entries.ConfigFlowContext(
            source=config_entries.SOURCE_RECONFIGURE, entry_id="Test"
        ),
    ],
)
async def test_start_flow_triggers_bucket_step(
    hass: HomeAssistant, context: config_entries.ConfigFlowContext
) -> None:
    """Test that starting the flow triggers the bucket step for all sources."""
    with patch(
        "homeassistant.components.aws_s3.config_flow.S3ConfigFlow.async_step_bucket",
        autospec=True,
        return_value=AsyncMock(),
        side_effect=lambda self, *_: ConfigFlowResult(
            type=FlowResultType.FORM,
            description_placeholders={},
            data_schema=vol.Schema({}),
            flow_id=self.flow_id,
        ),
    ) as mock:
        result = await hass.config_entries.flow.async_init(DOMAIN, context=context)
        assert result["flow_id"]
        assert result["flow_id"] in S3ConfigFlow._config_models
        mock.assert_called_once()


@pytest.mark.parametrize(
    ("context", "reason"),
    [
        (
            config_entries.ConfigFlowContext(source=config_entries.SOURCE_USER),
            "already_configured",
        ),
        (
            config_entries.ConfigFlowContext(
                source=config_entries.SOURCE_REAUTH, entry_id="Test"
            ),
            "reauth_successful",
        ),
        (
            config_entries.ConfigFlowContext(
                source=config_entries.SOURCE_RECONFIGURE, entry_id="Test"
            ),
            "reconfigure_successful",
        ),
    ],
)
async def test_end_flow_cleans_up_config_model(
    hass: HomeAssistant, context: config_entries.ConfigFlowContext, reason: str
) -> None:
    """Test that ending the flow cleans up the config model for all sources."""
    with patch(
        "homeassistant.components.aws_s3.config_flow.S3ConfigFlow.async_step_bucket",
        autospec=True,
        return_value=AsyncMock(),
        side_effect=lambda self, *_: ConfigFlowResult(
            type=FlowResultType.ABORT,
            reason=reason,
            description_placeholders={},
            flow_id=self.flow_id,
        ),
    ) as mock:
        result = await hass.config_entries.flow.async_init(DOMAIN, context=context)
        assert result["flow_id"]
        assert result["flow_id"] not in S3ConfigFlow._config_models
        assert len(S3ConfigFlow._config_models) == 0
        mock.assert_called_once()


###############
# USER FLOWS
###############


async def test_bucket_flow_user_initial(hass: HomeAssistant) -> None:
    """Test initial user bucket flow step returns correct schema and values."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context=config_entries.ConfigFlowContext(source=config_entries.SOURCE_USER),
    )
    assert result["step_id"] == "bucket"
    assert len(result["errors"]) == 0
    assert result["type"] == FlowResultType.FORM
    _validate_data_schema_output(
        result["data_schema"],
        expected_keys={
            CONF_BUCKET,
            CONF_ENDPOINT_URL,
            CONF_AUTH_MODE,
        },
        expected_readonly=set({}),
        expected_values={CONF_ENDPOINT_URL: DEFAULT_ENDPOINT_URL},
        expected_types={
            CONF_BUCKET: TextSelectorType.TEXT,
            CONF_ENDPOINT_URL: TextSelectorType.URL,
        },
    )



async def test_bucket_flow_user_create_implicit(hass: HomeAssistant) -> None:
    """Test user bucket flow creates entry with implicit credentials."""
    expected_keys = {
        CONF_BUCKET,
        CONF_ENDPOINT_URL,
        CONF_AUTH_MODE,
    }
    user_input = {
        k: v for k, v in USER_INPUT_VALID_IMPLICIT.items() if k in expected_keys
    }
    flow = await hass.config_entries.flow.async_init(
        DOMAIN,
        context=config_entries.ConfigFlowContext(source=config_entries.SOURCE_USER),
    )
    with patch(
        "homeassistant.components.aws_s3.config_model.S3ConfigModel.async_validate_access",
        autospec=True,
        return_value=AsyncMock(),
        side_effect=lambda self, *_: _record_errors(self, {}),
    ) as mock:
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], user_input=user_input
        )
        mock.assert_called_once()
        assert not result.get("step_id")
        assert not result.get("errors")
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["flow_id"] == flow["flow_id"]
        assert result["data"] == USER_INPUT_VALID_IMPLICIT
        assert result["title"] == USER_INPUT_VALID_IMPLICIT[CONF_BUCKET]
        assert result["result"].state == config_entries.ConfigEntryState.LOADED


async def test_profile_flow_user_initial(hass: HomeAssistant) -> None:
    """Test initial user profile flow step returns correct schema and values."""
    bucket_expected_keys = {
        CONF_BUCKET,
        CONF_ENDPOINT_URL,
        CONF_AUTH_MODE,
    }
    bucket_user_input = {
        k: v for k, v in USER_INPUT_VALID_PROFILE.items() if k in bucket_expected_keys
    }
    flow = await hass.config_entries.flow.async_init(
        DOMAIN,
        context=config_entries.ConfigFlowContext(source=config_entries.SOURCE_USER),
    )
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], user_input=bucket_user_input
    )
    assert result["step_id"] == "profile"
    assert len(result["errors"]) == 0
    assert result["type"] == FlowResultType.FORM
    _validate_data_schema_output(
        result["data_schema"],
        expected_keys={CONF_PROFILE_NAME},
        expected_readonly=set({}),
        expected_values={},
        expected_types={CONF_PROFILE_NAME: TextSelectorType.TEXT},
    )


async def test_profile_flow_user_create(hass: HomeAssistant) -> None:
    """Test user profile flow creates entry with profile credentials."""
    bucket_expected_keys = {
        CONF_BUCKET,
        CONF_ENDPOINT_URL,
        CONF_AUTH_MODE,
    }
    bucket_user_input = {
        k: v for k, v in USER_INPUT_VALID_PROFILE.items() if k in bucket_expected_keys
    }
    profile_expected_keys = {
        CONF_PROFILE_NAME,
    }
    profile_user_input = {
        k: v for k, v in USER_INPUT_VALID_PROFILE.items() if k in profile_expected_keys
    }
    flow = await hass.config_entries.flow.async_init(
        DOMAIN,
        context=config_entries.ConfigFlowContext(source=config_entries.SOURCE_USER),
    )
    with patch(
        "homeassistant.components.aws_s3.config_model.S3ConfigModel.async_validate_access",
        autospec=True,
        return_value=AsyncMock(),
        side_effect=lambda self, *_: _record_errors(self, {}),
    ) as mock:
        await hass.config_entries.flow.async_configure(
            flow["flow_id"], user_input=bucket_user_input
        )
        mock.assert_not_called()
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], user_input=profile_user_input
        )
        mock.assert_called()
        assert not result.get("step_id")
        assert not result.get("errors")
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["flow_id"] == flow["flow_id"]
        assert result["data"] == USER_INPUT_VALID_PROFILE
        assert result["title"] == USER_INPUT_VALID_PROFILE[CONF_BUCKET]
        assert result["result"].state == config_entries.ConfigEntryState.LOADED

