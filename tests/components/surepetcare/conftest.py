"""Define fixtures available for all tests."""
from unittest.mock import patch

import pytest
from surepy import MESTART_RESOURCE

from . import MOCK_API_DATA


@pytest.fixture
async def surepetcare():
    """Mock the SurePetcare for easier testing."""
    with patch("surepy.SureAPIClient", autospec=True) as mock_client_class, patch(
        "surepy.find_token"
    ):
        client = mock_client_class.return_value
        client.resources = {MESTART_RESOURCE: {"data": MOCK_API_DATA}}
        yield client
