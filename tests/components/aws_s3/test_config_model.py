"""Test the AWS S3 config flow model."""

from itertools import combinations
from unittest.mock import patch

from botocore.exceptions import (
    ClientError,
    EndpointConnectionError,
    NoCredentialsError,
    ParamValidationError,
    ProfileNotFound,
    TokenRetrievalError,
)
import pytest

from homeassistant.components.aws_s3.config_model import S3ConfigModel
from homeassistant.components.aws_s3.const import (
    CONF_ACCESS_KEY_ID,
    CONF_AUTH_MODE,
    CONF_AUTH_MODE_EXPLICIT,
    CONF_AUTH_MODE_IMPLICIT,
    CONF_AUTH_MODE_PROFILE,
    CONF_BUCKET,
    CONF_ENDPOINT_URL,
    CONF_PROFILE_NAME,
    CONF_SECRET_ACCESS_KEY,
)

from .const import (
    TEST_INVALID,
    TEST_PROFILE_NAME,
    USER_INPUT_VALID_EXPLICIT,
    USER_INPUT_VALID_EXPLICIT_NO_MODE,
    USER_INPUT_VALID_IMPLICIT,
    USER_INPUT_VALID_IMPLICIT_NO_MODE,
    USER_INPUT_VALID_PROFILE,
    USER_INPUT_VALID_PROFILE_NO_MODE,
)

from tests.typing import MagicMock


def test_init() -> None:
    """Test initialization of S3ConfigModel and its default state."""
    model = S3ConfigModel()
    assert len(model) == 6
    assert model.keys() == {
        CONF_BUCKET,
        CONF_ENDPOINT_URL,
        CONF_AUTH_MODE,
        CONF_PROFILE_NAME,
        CONF_ACCESS_KEY_ID,
        CONF_SECRET_ACCESS_KEY,
    }
    assert all(x is None for x in model.values())
    assert model.has_errors(set(model.keys())) is False
