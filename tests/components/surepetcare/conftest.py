"""Define fixtures available for all tests."""
from unittest.mock import patch

import pytest
from surepy import MESTART_RESOURCE

from . import MOCK_API_DATA


async def _mock_call(method, resource):
    if method == "GET" and resource == MESTART_RESOURCE:
        return {"data": MOCK_API_DATA}


@pytest.fixture
async def surepetcare():
    """Mock the SurePetcare for easier testing."""
    with patch("surepy.SureAPIClient", autospec=True) as mock_client_class:
        client = mock_client_class.return_value
        client.resources = {}
        client.call = _mock_call
        client.get_token.return_value = "token"
        yield client
