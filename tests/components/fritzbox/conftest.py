"""Fixtures for the AVM Fritz!Box integration."""
from unittest.mock import Mock, patch

import pytest


@pytest.fixture(name="fritz")
def fritz_fixture() -> Mock:
    """Patch libraries."""
    with patch("homeassistant.components.fritzbox.socket") as socket1, patch(
        "homeassistant.components.fritzbox.config_flow.socket"
    ) as socket2, patch("homeassistant.components.fritzbox.Fritzhome") as fritz, patch(
        "homeassistant.components.fritzbox.config_flow.Fritzhome"
    ):
        socket1.gethostbyname.return_value = "FAKE_IP_ADDRESS"
        socket2.gethostbyname.return_value = "FAKE_IP_ADDRESS"
        yield fritz
