"""Define fixtures for Bosch Alarm tests."""

from collections.abc import Generator
from unittest.mock import patch

import pytest


@pytest.fixture(name="setup_bosch_alarm")
def setup_bosch_alarm_fixture(request: pytest.FixtureRequest) -> Generator[None]:
    """Define a fixture to set up Bosch Alarm."""

    async def connect(self, load_selector):
        self.model = request.param

    with (
        patch("bosch_alarm_mode2.panel.Panel.connect", connect),
    ):
        yield request.param
