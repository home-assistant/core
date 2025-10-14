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
)

from tests.common import ConfigFlowResult, MockConfigEntry

####################
# HELPER FUNCTIONS
####################


def _validate_data_schema_output(
    data_schema: vol.Schema,
    expected_keys: set[str],
    expected_types: dict[str, str],
    expected_values: dict[str, str],
) -> None:
    """Validate an outputted data schema against expected keys, types, and values."""
    schema_detail = {
        k.schema: (k, data_schema.schema[k].config) for k in data_schema.schema
    }

    assert schema_detail.keys() == expected_keys

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


async def test_start_flow_triggers_bucket_step(hass: HomeAssistant) -> None:
    """Test that starting the flow triggers the bucket step."""
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
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context=config_entries.ConfigFlowContext(source=config_entries.SOURCE_USER),
        )
        assert result["flow_id"]
        assert result["flow_id"] in S3ConfigFlow._config_models
        mock.assert_called_once()


async def test_end_flow_cleans_up_config_model(hass: HomeAssistant) -> None:
    """Test that ending the flow cleans up the config model."""
    with patch(
        "homeassistant.components.aws_s3.config_flow.S3ConfigFlow.async_step_bucket",
        autospec=True,
        return_value=AsyncMock(),
        side_effect=lambda self, *_: ConfigFlowResult(
            type=FlowResultType.ABORT,
            reason="already_configured",
            description_placeholders={},
            flow_id=self.flow_id,
        ),
    ) as mock:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context=config_entries.ConfigFlowContext(source=config_entries.SOURCE_USER),
        )
        assert result["flow_id"]
        assert result["flow_id"] not in S3ConfigFlow._config_models
        assert len(S3ConfigFlow._config_models) == 0
        mock.assert_called_once()
