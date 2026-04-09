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
from homeassistant.const import ATTR_ENTITY_ID, Platform
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
    """Test cover entities are created for devices with openCloseStatus."""
    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_cover_open(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test opening a cover."""
    await setup_integration(hass, mock_config_entry, [Platform.COVER])

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
    await setup_integration(hass, mock_config_entry, [Platform.COVER])

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
    await setup_integration(hass, mock_config_entry, [Platform.COVER])

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
    await setup_integration(hass, mock_config_entry, [Platform.COVER])

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
    """Test cover reports closed state from openCloseStatus."""
    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    state = hass.states.get("cover.device_1")
    assert state is not None
    assert state.state == "closed"


async def test_cover_state_open(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test cover reports open state from openCloseStatus."""
    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    state = hass.states.get("cover.device_2")
    assert state is not None
    assert state.state == "open"


async def test_cover_state_unknown_when_status_unavailable(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test no covers created when status API fails."""
    mock_api_client.async_get_device_status.side_effect = FlussApiClientError(
        "Status unavailable"
    )

    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    # No covers should be created since no valid openCloseStatus
    assert hass.states.get("cover.device_1") is None
    assert hass.states.get("cover.device_2") is None


async def test_no_cover_when_status_missing(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that covers are not created when openCloseStatus is missing."""
    mock_api_client.async_get_device_status.side_effect = None
    mock_api_client.async_get_device_status.return_value = {"status": {}}

    await setup_integration(hass, mock_config_entry, [Platform.COVER])

    assert hass.states.get("cover.device_1") is None
    assert hass.states.get("cover.device_2") is None
