"""Define configuration parameters for scheduler tests."""
import pytest

from homeassistant.components.scheduler.schedule import Scheduler


@pytest.fixture
def scheduler(hass):
    """Fixture to mock the scheduler."""
    return Scheduler(hass)
