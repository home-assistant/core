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
