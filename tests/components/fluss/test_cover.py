"""Tests for the Fluss cover platform."""

from __future__ import annotations

from unittest.mock import AsyncMock

from fluss_api import FlussApiClientError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_covers(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test cover entities are created for each device."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_cover_open(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test opening a cover."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: "cover.device_1"},
        blocking=True,
    )

    mock_api_client.async_open_device.assert_called_once_with("2a303030sdj1")


async def test_cover_close(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test closing a cover."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: "cover.device_1"},
        blocking=True,
    )

    mock_api_client.async_close_device.assert_called_once_with("2a303030sdj1")


async def test_cover_open_error(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test cover open with API error."""
    await setup_integration(hass, mock_config_entry)

    mock_api_client.async_open_device.side_effect = FlussApiClientError("API Boom")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: "cover.device_1"},
            blocking=True,
        )


async def test_cover_close_error(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test cover close with API error."""
    await setup_integration(hass, mock_config_entry)

    mock_api_client.async_close_device.side_effect = FlussApiClientError("API Boom")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: "cover.device_1"},
            blocking=True,
        )


async def test_cover_state_closed(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test cover reports closed state."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("cover.device_1")
    assert state is not None
    assert state.state == "closed"


async def test_cover_state_open(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test cover reports open state."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("cover.device_2")
    assert state is not None
    assert state.state == "open"
