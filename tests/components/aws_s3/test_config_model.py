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


@pytest.mark.parametrize(
    ("data"),
    [
        USER_INPUT_VALID_PROFILE_NO_MODE,
        USER_INPUT_VALID_PROFILE,
        USER_INPUT_VALID_EXPLICIT_NO_MODE,
        USER_INPUT_VALID_EXPLICIT,
        USER_INPUT_VALID_IMPLICIT_NO_MODE,
        USER_INPUT_VALID_IMPLICIT,
    ],
)
def test_from_dict(data: dict[str, str]) -> None:
    """Test loading values from a dictionary into the model."""
    model = S3ConfigModel()
    model.from_dict(data)
    for k, v in data.items():
        assert model[k] == v


@pytest.mark.parametrize(
    ("data"),
    [
        USER_INPUT_VALID_PROFILE_NO_MODE,
        USER_INPUT_VALID_PROFILE,
        USER_INPUT_VALID_EXPLICIT_NO_MODE,
        USER_INPUT_VALID_EXPLICIT,
        USER_INPUT_VALID_IMPLICIT_NO_MODE,
        USER_INPUT_VALID_IMPLICIT,
    ],
)
def test_as_dict_only(data: dict[str, str]) -> None:
    """Test as_dict returns only requested keys and handles invalid keys."""
    model = S3ConfigModel()
    model.from_dict(data)
    for combo_len in range(1, len(data) + 1):
        for combo in combinations(data.keys(), combo_len):
            test = model.as_dict(combo)
            assert len(test) == len(combo)
            for k, v in test.items():
                assert data[k] == v
    test = model.as_dict(set({}))
    assert len(test) == 0
    test = model.as_dict({CONF_BUCKET, "Invalid"})
    assert len(test) == 1
    assert CONF_BUCKET in test
    assert test[CONF_BUCKET] == data[CONF_BUCKET]


@pytest.mark.parametrize(
    ("data"),
    [
        USER_INPUT_VALID_PROFILE_NO_MODE,
        USER_INPUT_VALID_PROFILE,
        USER_INPUT_VALID_EXPLICIT_NO_MODE,
        USER_INPUT_VALID_EXPLICIT,
        USER_INPUT_VALID_IMPLICIT_NO_MODE,
        USER_INPUT_VALID_IMPLICIT,
    ],
)
def test_as_dict(data: dict[str, str]) -> None:
    """Test as_dict returns all keys by default and with None argument."""
    model = S3ConfigModel()
    model.from_dict(data)
    test = model.as_dict()
    assert len(test) == len(data)
    for k, v in test.items():
        assert data[k] == v
    test = model.as_dict(None)
    assert len(test) == len(data)
    for k, v in test.items():
        assert data[k] == v


def test_del_item() -> None:
    """Test deleting an item from the model removes the key."""
    model = S3ConfigModel()
    keys_before = set(model.keys())
    del model[CONF_BUCKET]
    keys_after = set(model.keys())
    assert keys_before - keys_after == {CONF_BUCKET}


@pytest.mark.parametrize(
    ("auth_mode", "expected_blank"),
    [
        (None, set({})),
        (CONF_AUTH_MODE_EXPLICIT, {CONF_PROFILE_NAME}),
        (CONF_AUTH_MODE_PROFILE, {CONF_ACCESS_KEY_ID, CONF_SECRET_ACCESS_KEY}),
        (
            CONF_AUTH_MODE_IMPLICIT,
            {CONF_ACCESS_KEY_ID, CONF_SECRET_ACCESS_KEY, CONF_PROFILE_NAME},
        ),
    ],
)
def test_set_item_auth_mode(auth_mode, expected_blank) -> None:
    """Test setting auth_mode blanks out the correct fields."""
    model = S3ConfigModel()
    model.from_dict(
        {
            CONF_PROFILE_NAME: "Set",
            CONF_SECRET_ACCESS_KEY: "Set",
            CONF_ACCESS_KEY_ID: "Set",
            CONF_BUCKET: "Set",
            CONF_ENDPOINT_URL: "Set",
        }
    )
    model[CONF_AUTH_MODE] = auth_mode
    assert all(v is None for v in model.as_dict(expected_blank).values())
    assert all(
        v == "Set"
        for v in model.as_dict(
            set(model.keys()) - expected_blank - {CONF_AUTH_MODE}
        ).values()
    )
    assert model[CONF_AUTH_MODE] == auth_mode


async def test_async_validate_access_success() -> None:
    """Test async_validate_access succeeds with valid explicit credentials."""
    model = S3ConfigModel()
    model.from_dict(USER_INPUT_VALID_EXPLICIT)
    await model.async_validate_access()
    assert not model.has_errors(set(model.keys()))


_validate_access_errors = [
    (
        USER_INPUT_VALID_EXPLICIT,
        ParamValidationError(report="Invalid bucket name"),
        {CONF_BUCKET: "invalid_bucket_name"},
    ),
    (
        USER_INPUT_VALID_IMPLICIT,
        ParamValidationError(report="Invalid bucket name"),
        {CONF_BUCKET: "invalid_bucket_name"},
    ),
    (
        USER_INPUT_VALID_PROFILE,
        ParamValidationError(report="Invalid bucket name"),
        {CONF_BUCKET: "invalid_bucket_name"},
    ),
    (
        USER_INPUT_VALID_EXPLICIT,
        ValueError(),
        {CONF_ENDPOINT_URL: "invalid_endpoint_url"},
    ),
    (
        USER_INPUT_VALID_IMPLICIT,
        ValueError(),
        {CONF_ENDPOINT_URL: "invalid_endpoint_url"},
    ),
    (
        USER_INPUT_VALID_PROFILE,
        ValueError(),
        {CONF_ENDPOINT_URL: "invalid_endpoint_url"},
    ),
    (
        USER_INPUT_VALID_EXPLICIT,
        NoCredentialsError(),
        {
            CONF_ACCESS_KEY_ID: "invalid_credentials_explicit",
            CONF_SECRET_ACCESS_KEY: "invalid_credentials_explicit",
        },
    ),
    (
        USER_INPUT_VALID_IMPLICIT,
        NoCredentialsError(),
        {CONF_AUTH_MODE: "no_credentials_implicit"},
    ),
    (
        USER_INPUT_VALID_PROFILE,
        NoCredentialsError(),
        {CONF_PROFILE_NAME: "no_credentials_profile"},
    ),
    (
        USER_INPUT_VALID_EXPLICIT,
        ProfileNotFound(profile=TEST_PROFILE_NAME[TEST_INVALID]),
        {
            CONF_ACCESS_KEY_ID: "invalid_credentials_explicit",
            CONF_SECRET_ACCESS_KEY: "invalid_credentials_explicit",
        },
    ),
    (
        USER_INPUT_VALID_IMPLICIT,
        ProfileNotFound(profile=TEST_PROFILE_NAME[TEST_INVALID]),
        {CONF_AUTH_MODE: "no_credentials_implicit"},
    ),
    (
        USER_INPUT_VALID_PROFILE,
        ProfileNotFound(profile=TEST_PROFILE_NAME[TEST_INVALID]),
        {CONF_PROFILE_NAME: "no_credentials_profile"},
    ),
    (
        USER_INPUT_VALID_EXPLICIT,
        ClientError(
            error_response={"Error": {"Code": "InvalidAccessKeyId"}},
            operation_name="head_bucket",
        ),
        {
            CONF_ACCESS_KEY_ID: "invalid_credentials_explicit",
            CONF_SECRET_ACCESS_KEY: "invalid_credentials_explicit",
        },
    ),
    (
        USER_INPUT_VALID_IMPLICIT,
        ClientError(
            error_response={"Error": {"Code": "InvalidAccessKeyId"}},
            operation_name="head_bucket",
        ),
        {CONF_AUTH_MODE: "invalid_credentials"},
    ),
    (
        USER_INPUT_VALID_PROFILE,
        ClientError(
            error_response={"Error": {"Code": "InvalidAccessKeyId"}},
            operation_name="head_bucket",
        ),
        {CONF_PROFILE_NAME: "invalid_credentials"},
    ),
    (
        USER_INPUT_VALID_EXPLICIT,
        TokenRetrievalError(provider="TestProvider", error_msg="Test error"),
        {
            CONF_ACCESS_KEY_ID: "invalid_credentials_explicit",
            CONF_SECRET_ACCESS_KEY: "invalid_credentials_explicit",
        },
    ),
    (
        USER_INPUT_VALID_IMPLICIT,
        TokenRetrievalError(provider="TestProvider", error_msg="Test error"),
        {CONF_AUTH_MODE: "invalid_credentials"},
    ),
    (
        USER_INPUT_VALID_PROFILE,
        TokenRetrievalError(provider="TestProvider", error_msg="Test error"),
        {CONF_PROFILE_NAME: "invalid_credentials"},
    ),
    (
        USER_INPUT_VALID_EXPLICIT,
        EndpointConnectionError(endpoint_url="https://example.com"),
        {CONF_ENDPOINT_URL: "cannot_connect"},
    ),
    (
        USER_INPUT_VALID_IMPLICIT,
        EndpointConnectionError(endpoint_url="https://example.com"),
        {CONF_ENDPOINT_URL: "cannot_connect"},
    ),
    (
        USER_INPUT_VALID_PROFILE,
        EndpointConnectionError(endpoint_url="https://example.com"),
        {CONF_ENDPOINT_URL: "cannot_connect"},
    ),
]


@pytest.mark.parametrize(
    ("data", "exception", "expected_errors"), _validate_access_errors
)
async def test_async_validate_access_session_errors(
    data: dict[str, str], exception: Exception, expected_errors: dict[str, str]
) -> None:
    """Test async_validate_access handles session creation errors and maps them to model errors."""
    model = S3ConfigModel()
    model.from_dict(data)
    with patch("aiobotocore.session.AioSession.__init__", side_effect=exception):
        await model.async_validate_access()
        errors = model.get_errors()
        assert errors == expected_errors


@pytest.mark.parametrize(
    ("data", "exception", "expected_errors"), _validate_access_errors
)
async def test_async_validate_access_client_errors(
    data: dict[str, str], exception: Exception, expected_errors: dict[str, str]
) -> None:
    """Test async_validate_access handles client creation errors and maps them to model errors."""
    model = S3ConfigModel()
    model.from_dict(data)
    with patch("aiobotocore.session.AioSession.create_client", side_effect=exception):
        await model.async_validate_access()
        errors = model.get_errors()
        assert errors == expected_errors


@pytest.mark.parametrize(
    ("data", "exception", "expected_errors"), _validate_access_errors
)
async def test_async_validate_access_bucket_head_errors(
    mock_client: MagicMock,
    data: dict[str, str],
    exception: Exception,
    expected_errors: dict[str, str],
) -> None:
    """Test async_validate_access handles head_bucket errors and maps them to model errors."""
    model = S3ConfigModel()
    model.from_dict(data)
    mock_client.head_bucket.side_effect = exception
    await model.async_validate_access()
    errors = model.get_errors()
    assert errors == expected_errors

