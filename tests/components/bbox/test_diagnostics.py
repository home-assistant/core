"""Tests for Bbox diagnostics."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from . import setup_integration
from .const import TEST_SERIAL_NUMBER

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_bbox_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test diagnostics."""
    await setup_integration(hass, mock_config_entry)

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert diagnostics == {
        "entry": {
            "data": {
                "base_url": "https://mabbox.bytel.fr/api/v1/",
                "password": REDACTED,
            },
            "options": {},
            "title": "Mock Title",
            "unique_id": TEST_SERIAL_NUMBER,
        },
        "data": {
            "router_info": {
                "model": "Bbox Test",
                "serial": TEST_SERIAL_NUMBER,
                "version": "1.0.0",
            },
            "connected_devices_count": 2,
            "last_update_success": True,
        },
    }


async def test_diagnostics_no_data(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_bbox_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test diagnostics when no data is available."""
    # Set up integration but mock coordinator to have no data
    mock_bbox_api.get_router_info.return_value = None
    mock_bbox_api.get_hosts.return_value = []

    await setup_integration(hass, mock_config_entry)

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert diagnostics == {
        "entry": {
            "data": {
                "base_url": "https://mabbox.bytel.fr/api/v1/",
                "password": REDACTED,
            },
            "options": {},
            "title": "Mock Title",
            "unique_id": TEST_SERIAL_NUMBER,
        },
        "data": {
            "router_info": {
                "model": None,
                "serial": None,
                "version": None,
            },
            "connected_devices_count": 0,
            "last_update_success": True,
        },
    }


async def test_diagnostics_update_failed(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_bbox_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test diagnostics when update has failed."""
    await setup_integration(hass, mock_config_entry)

    # Simulate a failed update by setting last_update_success to False
    mock_config_entry.runtime_data.last_update_success = False
    mock_config_entry.runtime_data.last_update_success_time = None

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert diagnostics == {
        "entry": {
            "data": {
                "base_url": "https://mabbox.bytel.fr/api/v1/",
                "password": REDACTED,
            },
            "options": {},
            "title": "Mock Title",
            "unique_id": TEST_SERIAL_NUMBER,
        },
        "data": {
            "router_info": {
                "model": "Bbox Test",
                "serial": TEST_SERIAL_NUMBER,
                "version": "1.0.0",
            },
            "connected_devices_count": 2,
            "last_update_success": False,
        },
    }
