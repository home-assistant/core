"""Tests for the AdGuard Home config flow."""

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import CONTENT_TYPE_JSON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the adguard update platform."""
    aioclient_mock.post(
        "https://127.0.0.1:3000/control/version.json",
        json={
            "new_version": "v0.107.59",
            "announcement": "AdGuard Home v0.107.59 is now available!",
            "announcement_url": "https://github.com/AdguardTeam/AdGuardHome/releases/tag/v0.107.59",
            "can_autoupdate": True,
            "disabled": False,
        },
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    with patch("homeassistant.components.adguard.PLATFORMS", [Platform.UPDATE]):
        await setup_integration(hass, mock_config_entry, aioclient_mock)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_update_disabled(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the adguard update is disabled."""
    aioclient_mock.post(
        "https://127.0.0.1:3000/control/version.json",
        json={"disabled": True},
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    with patch("homeassistant.components.adguard.PLATFORMS", [Platform.UPDATE]):
        await setup_integration(hass, mock_config_entry, aioclient_mock)

    assert not hass.states.async_all()
