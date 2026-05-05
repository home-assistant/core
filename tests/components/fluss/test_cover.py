"""Tests for the Fluss+ cover platform."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

from fluss_api import FlussApiClientError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_CLOSED,
    STATE_OPEN,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID_1 = "cover.device_1"
ENTITY_ID_2 = "cover.device_2"


def _status_side_effect(
    statuses: dict[str, dict[str, Any]],
    *,
    default_internet_connected: bool = True,
):
    """Return a side_effect callable that yields per-device status payloads."""

    async def _get_status(device_id: str) -> dict[str, Any]:
        return {
            "status": {
                "internetConnected": default_internet_connected,
                **statuses.get(device_id, {}),
            }
        }

    return _get_status


async def _setup_cover_only(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up integration with only the cover platform."""
    with patch("homeassistant.components.fluss.PLATFORMS", [Platform.COVER]):
        await setup_integration(hass, entry)


async def test_covers(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test cover entity registration."""
    mock_api_client.async_get_device_status.side_effect = _status_side_effect(
        {
            "2a303030sdj1": {"openCloseStatus": "Closed"},
            "ape93k9302j2": {"openCloseStatus": "Open"},
        }
    )
    await _setup_cover_only(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("status_value", "expected_state"),
    [
        ("Closed", STATE_CLOSED),
        ("closed", STATE_CLOSED),
        ("CLOSED", STATE_CLOSED),
        ("Open", STATE_OPEN),
        ("open", STATE_OPEN),
        (True, STATE_OPEN),
        (False, STATE_CLOSED),
        ("partially-open", STATE_UNKNOWN),
        (42, STATE_UNKNOWN),
    ],
)
async def test_cover_state_parsing(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    status_value: Any,
    expected_state: str,
) -> None:
    """Test is_closed mapping for string, boolean, and unknown values."""
    mock_api_client.async_get_device_status.side_effect = _status_side_effect(
        {
            "2a303030sdj1": {"openCloseStatus": status_value},
            "ape93k9302j2": {"openCloseStatus": status_value},
        }
    )
    await _setup_cover_only(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID_1)
    assert state is not None
    assert state.state == expected_state


async def test_open_cover(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test opening the cover calls the open API and refreshes."""
    mock_api_client.async_get_device_status.side_effect = _status_side_effect(
        {"2a303030sdj1": {"openCloseStatus": "Closed"}}
    )
    await _setup_cover_only(hass, mock_config_entry)
    mock_api_client.async_get_device_status.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: ENTITY_ID_1},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_api_client.async_open_device.assert_called_once_with("2a303030sdj1")
    assert mock_api_client.async_get_device_status.call_count >= 1


async def test_close_cover(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test closing the cover calls the close API and refreshes."""
    mock_api_client.async_get_device_status.side_effect = _status_side_effect(
        {"2a303030sdj1": {"openCloseStatus": "Open"}}
    )
    await _setup_cover_only(hass, mock_config_entry)
    mock_api_client.async_get_device_status.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: ENTITY_ID_1},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_api_client.async_close_device.assert_called_once_with("2a303030sdj1")
    assert mock_api_client.async_get_device_status.call_count >= 1


@pytest.mark.parametrize(
    ("service", "method"),
    [
        (SERVICE_OPEN_COVER, "async_open_device"),
        (SERVICE_CLOSE_COVER, "async_close_device"),
    ],
)
async def test_cover_command_error(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    method: str,
) -> None:
    """Test library errors are translated to HomeAssistantError."""
    mock_api_client.async_get_device_status.side_effect = _status_side_effect(
        {"2a303030sdj1": {"openCloseStatus": "Closed"}}
    )
    await _setup_cover_only(hass, mock_config_entry)

    getattr(mock_api_client, method).side_effect = FlussApiClientError("boom")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            COVER_DOMAIN,
            service,
            {ATTR_ENTITY_ID: ENTITY_ID_1},
            blocking=True,
        )


async def test_mixed_device_dispatch(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test cover XOR button per device based on openCloseStatus."""
    mock_api_client.async_get_device_status.side_effect = _status_side_effect(
        {"2a303030sdj1": {"openCloseStatus": "Closed"}}
    )
    await setup_integration(hass, mock_config_entry)

    assert entity_registry.async_get("cover.device_1") is not None
    assert entity_registry.async_get("button.device_1") is None
    assert entity_registry.async_get("button.device_2") is not None
    assert entity_registry.async_get("cover.device_2") is None
