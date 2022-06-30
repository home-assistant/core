"""Conftest for pushbullet integration."""

import json
from unittest.mock import patch

from pushbullet import PushBullet
import pytest

from tests.common import load_fixture


@pytest.fixture(autouse=True)
def mock_pushbullet():
    """Mock pushbullet."""
    with patch.object(
        PushBullet,
        "_get_data",
        return_value=json.loads(load_fixture("devices.json", "pushbullet")),
    ) as mock_client:
        yield mock_client
