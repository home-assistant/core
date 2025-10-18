"""Fixtures for Sony Projector tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.sony_projector.client import ProjectorState
from homeassistant.components.sony_projector.const import (
    CONF_MODEL,
    CONF_SERIAL,
    CONF_TITLE,
    DATA_DISCOVERY,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_projector_state() -> ProjectorState:
    """Return a mocked projector state."""

    return ProjectorState(
        is_on=True,
        current_input="HDMI 1",
        inputs=["HDMI 1", "HDMI 2"],
        picture_mute=False,
        lamp_hours=125,
        aspect_ratio="NORMAL",
        aspect_ratio_options=["NORMAL", "SQUEEZE"],
        picture_mode="CINEMA_FILM_1",
        picture_mode_options=["CINEMA_FILM_1", "GAME"],
        model="VPL-Test",
        serial="123456",
    )


@pytest.fixture
def mock_projector_client(mock_projector_state: ProjectorState) -> MagicMock:
    """Return a mocked projector client."""

    client = MagicMock()
    client.async_refresh_device_info = AsyncMock()
    client.async_get_state = AsyncMock(return_value=mock_projector_state)
    client.async_set_power = AsyncMock()
    client.async_set_input = AsyncMock()
    client.async_toggle_picture_mute = AsyncMock()
    client.async_set_aspect_ratio = AsyncMock()
    client.async_set_picture_mode = AsyncMock()
    client.serial = mock_projector_state.serial
    client.model = mock_projector_state.model
    return client


@pytest.fixture
def mock_client_class(
    mock_projector_client: MagicMock,
) -> Generator[MagicMock]:
    """Patch the projector client constructor."""

    with (
        patch(
            "homeassistant.components.sony_projector.client.ProjectorClient",
            return_value=mock_projector_client,
        ) as mock_cls,
        patch(
            "homeassistant.components.sony_projector.config_flow.ProjectorClient",
            return_value=mock_projector_client,
        ),
        patch(
            "homeassistant.components.sony_projector.ProjectorClient",
            return_value=mock_projector_client,
        ),
    ):
        yield mock_cls


@pytest.fixture
def mock_discovery() -> Generator[AsyncMock]:
    """Patch discovery for config flow tests."""

    with patch(
        "homeassistant.components.sony_projector.config_flow.async_discover",
        AsyncMock(return_value=[]),
    ) as discover:
        yield discover


@pytest.fixture
def mock_discovery_listener() -> Generator[AsyncMock]:
    """Patch the passive discovery listener."""

    async def _start_listener(hass: HomeAssistant) -> None:
        hass.data.setdefault(DOMAIN, {})[DATA_DISCOVERY] = None

    with patch(
        "homeassistant.components.sony_projector.async_start_listener",
        AsyncMock(side_effect=_start_listener),
    ) as listener:
        yield listener


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry for the integration."""

    return MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_SERIAL: "123456",
            CONF_MODEL: "VPL-Test",
            CONF_TITLE: DEFAULT_NAME,
        },
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client_class: MagicMock,
    mock_discovery_listener: AsyncMock,
) -> MockConfigEntry:
    """Set up the Sony Projector integration for testing."""

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
