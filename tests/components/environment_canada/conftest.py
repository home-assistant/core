"""Common fixture for Environment Canada tests."""

import contextlib
from datetime import datetime
import json

from env_canada.ec_weather import MetaData
import pytest

from homeassistant.components.environment_canada.const import DOMAIN

from . import FIXTURE_USER_INPUT

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=FIXTURE_USER_INPUT,
        title="Home",
    )


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
