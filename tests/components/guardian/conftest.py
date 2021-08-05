"""Define fixtures for Elexa Guardian tests."""
from unittest.mock import patch

import pytest


@pytest.fixture()
def ping_client():
    """Define a patched client that returns a successful ping response."""
    with patch(
        "homeassistant.components.guardian.async_setup_entry", return_value=True
    ), patch("aioguardian.client.Client.connect"), patch(
        "aioguardian.commands.system.SystemCommands.ping",
        return_value={"command": 0, "status": "ok", "data": {"uid": "ABCDEF123456"}},
    ), patch(
        "aioguardian.client.Client.disconnect"
    ):
        yield
