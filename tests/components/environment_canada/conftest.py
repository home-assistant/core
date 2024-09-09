"""Common fixture for Environment Canada tests."""

import contextlib
from datetime import datetime
import json

import pytest

from tests.common import load_fixture


@pytest.fixture
def ec_data():
    """Load Environment Canada data."""

    def date_hook(weather):
        """Convert timestamp string to datetime."""

        if t := weather.get("timestamp"):
            with contextlib.suppress(ValueError):
                weather["timestamp"] = datetime.fromisoformat(t)
        return weather

    return json.loads(
        load_fixture("environment_canada/current_conditions_data.json"),
        object_hook=date_hook,
    )
