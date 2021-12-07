"""Provide common fixtures."""
import time
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def client() -> Generator[None, MagicMock, None]:
    """Mock balboa."""
    with patch(
        "homeassistant.components.balboa.BalboaSpaWifi", autospec=True
    ) as mock_balboa:
        client = mock_balboa.return_value
        client.host = None
        client.port = None
        client.connected = True
        client.lastupd = time.time()
        client.new_data_cb = None
        client.connect.return_value = True
        client.get_macaddr.return_value = "ef:ef:ef:c0:ff:ee"
        client.get_model_name.return_value = "FakeSpa"
        client.get_ssid.return_value = "V0.0"
        yield client
