"""Fixtures for Moon integration tests."""

from collections.abc import Generator
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from skyfield.jpllib import SpiceKernel
from skyfield.timelib import Timescale
from skyfield.units import Angle

from homeassistant.components.moon.const import DOMAIN
from homeassistant.components.moon.helpers import MoonData

from tests.common import MockConfigEntry


@pytest.fixture
def moon_data() -> MoonData:
    """Return mocked astronomy data for the Moon integration tests."""
    return MoonData(cast(SpiceKernel, MagicMock()), cast(Timescale, MagicMock()))


@pytest.fixture(autouse=True)
def mock_moon_data(moon_data: MoonData) -> Generator[None]:
    """Avoid network downloads during integration tests."""
    with (
        patch("homeassistant.components.moon.load_moon_data", return_value=moon_data),
        patch(
            "homeassistant.components.moon.helpers.almanac.moon_phase",
            return_value=Angle(degrees=0),
        ),
    ):
        yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Moon",
        domain=DOMAIN,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch("homeassistant.components.moon.async_setup_entry", return_value=True):
        yield
