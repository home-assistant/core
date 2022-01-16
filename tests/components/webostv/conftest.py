"""Common fixtures and objects for the LG webOS integration tests."""
from unittest.mock import patch

import pytest

from tests.common import async_mock_service


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture(name="client")
def client_fixture():
    """Patch of client library for tests."""
    with patch(
        "homeassistant.components.webostv.WebOsClient", autospec=True
    ) as mock_client_class:
        client = mock_client_class.return_value
        client.hello_info = {"deviceUUID": "some-fake-uuid"}
        client.software_info = {"device_id": "00:01:02:03:04:05"}
        client.system_info = {"modelName": "TVFAKE"}
        client.client_key = "0123456789"
        client.apps = {0: {"title": "Applicaiton01"}}
        client.inputs = {0: {"label": "Input01"}, 1: {"label": "Input02"}}

        yield client
