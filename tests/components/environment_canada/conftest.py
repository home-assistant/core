"""Common fixture for Environment Canada tests."""

import contextlib
from datetime import datetime
import json

from env_canada.ec_weather import MetaData
import pytest

from tests.common import load_fixture


@pytest.fixture
def ec_data():
    """Load Environment Canada data."""

    def data_hook(weather):
        """Convert timestamp string to datetime."""

        if t := weather.get("timestamp"):
            with contextlib.suppress(ValueError):
                weather["timestamp"] = datetime.fromisoformat(t)
        elif t := weather.get("period"):
            with contextlib.suppress(ValueError):
                weather["period"] = datetime.fromisoformat(t)
        if t := weather.get("metadata"):
            weather["metadata"] = MetaData(**t)
        return weather

    return json.loads(
        load_fixture("environment_canada/current_conditions_data.json"),
        object_hook=data_hook,
    )
