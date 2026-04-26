"""Common fixtures for the PJLink tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from aiopjlink import Power, Sources
import pytest

from homeassistant.components.pjlink.const import DOMAIN

from .const import DEFAULT_DATA

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.pjlink.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""

    return MockConfigEntry(
        version=1, domain=DOMAIN, title="test name", data=DEFAULT_DATA
    )


@pytest.fixture
def mock_pjlink() -> Generator[MagicMock]:
    """Mock the PJLink Projector in the config flow."""

    with (
        patch("homeassistant.components.pjlink.PJLink") as mock_init,
        patch("homeassistant.components.pjlink.config_flow.PJLink") as mock_config,
    ):
        instance = MagicMock()

        instance.info = MagicMock()
        instance.info.projector_name = AsyncMock(return_value="test name")

        instance.power = MagicMock()
        instance.power.get = AsyncMock(return_value=Power.State.OFF)
        instance.power.turn_off = AsyncMock()
        instance.power.turn_on = AsyncMock()

        instance.sources = MagicMock()
        instance.sources.get = AsyncMock(return_value=(Sources.Mode.DIGITAL, 1))
        instance.sources.available = AsyncMock(
            return_value=[
                (Sources.Mode.DIGITAL, 1),
                (Sources.Mode.DIGITAL, 2),
                (Sources.Mode.VIDEO, 1),
            ]
        )
        instance.sources.set = AsyncMock()

        instance.mute = MagicMock()
        instance.mute.status = AsyncMock(return_value=(False, True))
        instance.mute.audio = AsyncMock()

        mock_init.return_value = instance
        mock_config.return_value = instance
        yield instance
