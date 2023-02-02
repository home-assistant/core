"""Test fixtures for the Imazu Wall Pad integration."""
from itertools import cycle
from unittest.mock import patch

import pytest

from .const import IP, PORT
from .mock import MockImazuClient


@pytest.fixture
def mock_imazu_client():
    """Mock connecting to a imazu client."""
    client = MockImazuClient(IP, PORT)
    with patch(
        "homeassistant.components.imazu_wall_pad.gateway.ImazuClient",
        side_effect=cycle([client]),
    ), patch(
        "homeassistant.components.imazu_wall_pad.config_flow.ImazuClient",
        side_effect=cycle([client]),
    ):
        yield client
