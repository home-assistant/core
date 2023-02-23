"""Global fixtures for Roborock integration."""
from unittest.mock import patch

import pytest

from .mock_data import PROP


@pytest.fixture(name="bypass_api_fixture")
def bypass_api_fixture():
    """Skip calls to the API."""
    with patch("roborock.RoborockMqttClient.connect"), patch(
        "roborock.RoborockMqttClient.send_command"
    ), patch("roborock.api.mqtt"), patch(
        "roborock.RoborockMqttClient.get_prop", return_value=PROP
    ):
        yield
