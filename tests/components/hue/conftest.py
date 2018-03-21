"""Fixtures for Hue tests."""
from unittest.mock import patch

import pytest

from tests.common import mock_coro_func


@pytest.fixture
def mock_bridge():
    """Mock the HueBridge from initializing."""
    with patch('homeassistant.components.hue._find_username_from_config',
               return_value=None), \
            patch('homeassistant.components.hue.HueBridge') as mock_bridge:
        mock_bridge().async_setup = mock_coro_func()
        mock_bridge.reset_mock()
        yield mock_bridge
