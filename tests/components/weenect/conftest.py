"""Global fixtures for Weenect integration."""
import json
from unittest.mock import AsyncMock, patch

import pytest

from tests.common import load_fixture


@pytest.fixture(name="bypass_get_trackers")
def bypass_get_trackers_fixture():
    """Skip calls to get data from weenect."""
    with patch("aioweenect.AioWeenect.get_trackers"):
        yield


@pytest.fixture(name="bypass_login")
def bypass_login_fixture():
    """Skip calls to login to weenect."""
    with patch("aioweenect.AioWeenect.login"):
        yield


@pytest.fixture(name="error_on_get_trackers")
def error_get_trackers_fixture():
    """Simulate error when retrieving data from weenect."""
    with patch(
        "aioweenect.AioWeenect.get_trackers",
        side_effect=Exception,
    ):
        yield


@pytest.fixture(name="get_trackers")
def get_trackers_fixture():
    """Simulate static result when retrieving data from weenect."""
    with patch(
        "aioweenect.AioWeenect.get_trackers",
        side_effect=AsyncMock(
            return_value=json.loads(load_fixture("weenect/get_trackers_response.json"))
        ),
    ):
        yield
