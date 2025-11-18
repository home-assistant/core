"""Tests for the AdGuard Home sensor entities."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import CONTENT_TYPE_JSON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the adguard sensor platform."""
    aioclient_mock.get(
        "https://127.0.0.1:3000/control/stats",
        json={
            "num_dns_queries": 666,
            "num_blocked_filtering": 1337,
            "num_replaced_safebrowsing": 42,
            "num_replaced_parental": 13,
            "num_replaced_safesearch": 18,
            "avg_processing_time": 0.03141,
        },
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )
    aioclient_mock.get(
        "https://127.0.0.1:3000/control/filtering/status",
        json={"filters": [{"rules_count": 99}, {"rules_count": 1}]},
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    with patch("homeassistant.components.adguard.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry, aioclient_mock)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
