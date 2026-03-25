"""Fixtures for ADAM Audio integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.adam_audio.client import AdamAudioState
from homeassistant.components.adam_audio.const import (
    CONF_DESCRIPTION,
    CONF_DEVICE_NAME,
    CONF_HOST,
    CONF_PORT,
    CONF_SERIAL,
    DOMAIN,
)

from tests.common import MockConfigEntry

MOCK_HOST = "192.168.1.100"
MOCK_PORT = 49494
MOCK_DEVICE_NAME = "ASeries-test01"
MOCK_DESCRIPTION = "Left Speaker"
MOCK_SERIAL = "SN-12345"


@pytest.fixture(autouse=True)
def clear_state_leakage() -> None:
    """Clear global state to prevent leakage across tests.

    Note: With state moved to hass.data[DOMAIN], the fresh 'hass' fixture
    provided by pytest-homeassistant-custom-component already handles
    most resets. This fixture is kept for future-proofing.
    """


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title=MOCK_DESCRIPTION,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_DEVICE_NAME: MOCK_DEVICE_NAME,
            CONF_DESCRIPTION: MOCK_DESCRIPTION,
            CONF_SERIAL: MOCK_SERIAL,
        },
        source="user",
        unique_id=MOCK_SERIAL,
        options={},
        discovery_keys={},
    )


@pytest.fixture
def mock_state() -> AdamAudioState:
    """Create a default mock device state."""
    return AdamAudioState(
        mute=False,
        sleep=False,
        input_source=1,
        voicing=0,
        bass=0,
        desk=0,
        presence=0,
        treble=0,
    )


@pytest.fixture
def mock_client(mock_state: AdamAudioState) -> Generator[MagicMock]:
    """Create a mock AdamAudioClient."""
    with (
        patch(
            "homeassistant.components.adam_audio.coordinator.AdamAudioClient",
            autospec=True,
        ) as mock_coord,
        patch(
            "homeassistant.components.adam_audio.config_flow.AdamAudioClient",
            autospec=True,
        ) as mock_flow,
    ):
        # Both mocks point to the same return value
        client = mock_coord.return_value
        mock_flow.return_value = client
        client.host = MOCK_HOST
        client.port = MOCK_PORT
        client.available = True
        client.device_name = MOCK_DEVICE_NAME
        client.description = MOCK_DESCRIPTION
        client.serial = MOCK_SERIAL
        client.state = mock_state
        client.async_setup = AsyncMock(return_value=True)
        client.async_shutdown = AsyncMock()
        client.async_fetch_state = AsyncMock(return_value=True)
        client.async_set_mute = AsyncMock()
        client.async_set_sleep = AsyncMock()
        client.async_set_input = AsyncMock()
        client.async_set_voicing = AsyncMock()
        client.async_set_bass = AsyncMock()
        client.async_set_desk = AsyncMock()
        client.async_set_presence = AsyncMock()
        client.async_set_treble = AsyncMock()
        yield client
