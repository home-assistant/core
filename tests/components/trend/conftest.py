"""Fixtures for the trend component tests."""
import pytest

from homeassistant.components.trend.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
async def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a MockConfigEntry for testing."""
    return MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My trend",
            "entity_id": "sensor.cpu_temp",
            "invert": False,
            "max_samples": 2.0,
            "min_gradient": 0.0,
            "sample_duration": 0.0,
        },
        title="My trend",
    )
