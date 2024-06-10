"""Configure py.test."""

import json
from unittest.mock import patch

import pytest

from .const import VALID_ACCESS_TOKEN, VALID_ACCOUNT_ID

from tests.common import load_fixture


@pytest.fixture(name="laundrify_setup_entry")
def laundrify_setup_entry_fixture():
    """Mock laundrify setup entry function."""
    with patch(
        "homeassistant.components.laundrify.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="laundrify_exchange_code")
def laundrify_exchange_code_fixture():
    """Mock laundrify exchange_auth_code function."""
    with patch(
        "laundrify_aio.LaundrifyAPI.exchange_auth_code",
        return_value=VALID_ACCESS_TOKEN,
    ) as exchange_code_mock:
        yield exchange_code_mock


@pytest.fixture(name="laundrify_validate_token")
def laundrify_validate_token_fixture():
    """Mock laundrify validate_token function."""
    with patch(
        "laundrify_aio.LaundrifyAPI.validate_token",
        return_value=True,
    ) as validate_token_mock:
        yield validate_token_mock


@pytest.fixture(name="laundrify_api_mock", autouse=True)
def laundrify_api_fixture(laundrify_exchange_code, laundrify_validate_token):
    """Mock valid laundrify API responses."""
    with (
        patch(
            "laundrify_aio.LaundrifyAPI.get_account_id",
            return_value=VALID_ACCOUNT_ID,
        ),
        patch(
            "laundrify_aio.LaundrifyAPI.get_machines",
            return_value=json.loads(load_fixture("laundrify/machines.json")),
        ) as get_machines_mock,
    ):
        yield get_machines_mock
