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

