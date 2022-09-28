"""Tests for Fritz!Tools update platform."""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

from homeassistant.components.mikrotik.const import FIRMWARE, MIKROTIK_SERVICES
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN
from homeassistant.components.update.const import SERVICE_INSTALL
from homeassistant.core import HomeAssistant

from . import UPDATE_INSTALLED_INFO, setup_mikrotik_entry


def mock_command(self, cmd: str, params: dict[str, Any] | None = None) -> Any:
    """Mock the Mikrotik command method."""
    if cmd == f"{MIKROTIK_SERVICES[FIRMWARE]}/install":
        return [UPDATE_INSTALLED_INFO]


async def test_update_available(hass: HomeAssistant) -> None:
    """Test update entities."""

    await setup_mikrotik_entry(hass)

    update = hass.states.get("update.firmware")
    assert update is not None
    assert update.state == "on"
    assert update.attributes.get("installed_version") == "1.0"
    assert update.attributes.get("latest_version") == "2.0"
    assert (
        update.attributes.get("release_url")
        == "https://mikrotik.com/download/changelogs"
    )


async def test_available_update_can_be_installed(hass: HomeAssistant) -> None:
    """Test installing update."""

    await setup_mikrotik_entry(hass)

    update = hass.states.get("update.firmware")
    assert update is not None
    assert update.state == "on"
    assert update.attributes.get("installed_version") == "1.0"
    assert update.attributes.get("latest_version") == "2.0"
    assert (
        update.attributes.get("release_url")
        == "https://mikrotik.com/download/changelogs"
    )

    with patch(
        "homeassistant.components.mikrotik.hub.MikrotikData.command", new=mock_command
    ):
        assert await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {"entity_id": "update.firmware"},
            blocking=True,
        )

    update = hass.states.get("update.firmware")
    assert update is not None
    assert update.state == "off"
    assert update.attributes.get("installed_version") == "2.0"
    assert update.attributes.get("latest_version") == "2.0"
