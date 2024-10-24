"""Test sky_remote remote."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.sky_remote.remote import SkyRemote
from homeassistant.exceptions import ServiceValidationError


def test_send_command() -> None:
    """Test "send_command" method."""
    mock_remote = MagicMock()
    remote = SkyRemote(mock_remote, "test_remote")
    remote.send_command(
        ["sky"],
    )
    mock_remote.send_keys.assert_called_once_with(["sky"])


def test_send_invalid_command() -> None:
    """Test "send_command" method."""
    mock_remote = MagicMock()
    remote = SkyRemote(mock_remote, "test_remote")
    with pytest.raises(ServiceValidationError):
        remote.send_command(
            ["apple"],
        )
    mock_remote.send_keys.assert_not_called()
