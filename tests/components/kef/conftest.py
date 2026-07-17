"""Fixtures for the KEF integration tests."""

from collections.abc import Coroutine, Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.kef.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry


class FakeKefConnector:
    """Fake KefAsyncConnector for testing."""

    def __init__(self) -> None:
        """Initialize the fake connector."""
        self._volume = 50
        self._source = "wifi"
        self._is_playing = False
        self._mac_address = "aa:bb:cc:dd:ee:ff"
        self._speaker_name = "Test KEF Speaker"
        self._speaker_model = "XIO"
        self.mac_address_error: Exception | None = None
        self.power_on = AsyncMock()
        self.shutdown = AsyncMock()
        self.mute = AsyncMock()
        self.unmute = AsyncMock()
        self.toggle_play_pause = AsyncMock()
        self.next_track = AsyncMock()
        self.previous_track = AsyncMock()
        self.set_volume = AsyncMock()
        self.set_source = AsyncMock()
        self.set_status = AsyncMock()

    @property
    def volume(self) -> Coroutine[Any, Any, int]:
        """Return an awaitable volume."""

        async def _get() -> int:
            return self._volume

        return _get()

    @property
    def source(self) -> Coroutine[Any, Any, str]:
        """Return an awaitable source."""

        async def _get() -> str:
            return self._source

        return _get()

    @property
    def is_playing(self) -> Coroutine[Any, Any, bool]:
        """Return an awaitable playing state."""

        async def _get() -> bool:
            return self._is_playing

        return _get()

    @property
    def mac_address(self) -> Coroutine[Any, Any, str]:
        """Return an awaitable MAC address."""

        async def _get() -> str:
            if self.mac_address_error is not None:
                raise self.mac_address_error
            return self._mac_address

        return _get()

    @property
    def speaker_name(self) -> Coroutine[Any, Any, str]:
        """Return an awaitable speaker name."""

        async def _get() -> str:
            return self._speaker_name

        return _get()

    async def get_speaker_model(self) -> str:
        """Return the speaker model."""
        return self._speaker_model

    async def get_song_information(self) -> dict[str, str | None]:
        """Return fake song information."""
        return {
            "title": None,
            "artist": None,
            "album": None,
            "cover_url": None,
        }


@pytest.fixture
def mock_connector() -> Generator[FakeKefConnector]:
    """Patch the KEF connector."""
    connector = FakeKefConnector()
    with (
        patch(
            "pykefcontrol.kef_connector.KefAsyncConnector",
            return_value=connector,
        ),
        patch(
            "homeassistant.components.kef.KefAsyncConnector",
            return_value=connector,
        ),
        patch(
            "homeassistant.components.kef.config_flow.KefAsyncConnector",
            return_value=connector,
        ),
    ):
        yield connector


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock KEF config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test KEF Speaker",
        unique_id="aa:bb:cc:dd:ee:ff",
        data={CONF_HOST: "192.168.1.100", "model": "XIO"},
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a KEF config entry."""
    with patch(
        "homeassistant.components.kef.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup
