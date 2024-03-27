"""switch conftest."""

import pytest

from homeassistant.const import STATE_OFF, STATE_ON

from tests.common import MockToggleEntity
from tests.components.light.conftest import mock_light_profiles  # noqa: F401


@pytest.fixture
def mock_switch_entities() -> list[MockToggleEntity]:
    """Return a list of mock switch entities."""
    return [
        MockToggleEntity("AC", STATE_ON),
        MockToggleEntity("AC", STATE_OFF),
        MockToggleEntity(None, STATE_OFF),
    ]
