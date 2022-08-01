"""Tests for Fritz!Tools update platform."""

from unittest.mock import patch

from homeassistant.components.mikrotik.const import FIRMWARE, MIKROTIK_SERVICES
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN
from homeassistant.components.update.const import SERVICE_INSTALL
from homeassistant.core import HomeAssistant

from . import MOCK_UPDATE_INFO, setup_mikrotik_entry


def mock_command(self, cmd, params=None):
    """Mock the Mikrotik command method."""
    if cmd == f"{MIKROTIK_SERVICES[FIRMWARE]}/install":
        return [MOCK_UPDATE_INFO]


async def test_update_available(hass: HomeAssistant) -> None:
    """Test update entities."""

    await setup_mikrotik_entry(hass)

    update = hass.states.get("update.mikrotik_update")
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

    update = hass.states.get("update.mikrotik_update")
    assert update is not None
    assert update.state == "on"
    assert update.attributes.get("installed_version") == "1.0"
    assert update.attributes.get("latest_version") == "2.0"
    assert (
        update.attributes.get("release_url")
        == "https://mikrotik.com/download/changelogs"
    )

    MOCK_UPDATE_INFO["installed-version"] = "2.0"
    MOCK_UPDATE_INFO["status"] = "System is already up to date"

    with patch(
        "homeassistant.components.mikrotik.hub.MikrotikData.command", new=mock_command
    ):
        assert await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {"entity_id": "update.mikrotik_update"},
            blocking=True,
        )

    update = hass.states.get("update.mikrotik_update")
    assert update is not None
    assert update.state == "off"
    assert update.attributes.get("installed_version") == "2.0"
    assert update.attributes.get("latest_version") == "2.0"
