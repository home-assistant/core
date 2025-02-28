"""Unit tests for the VegeHub integration's sensor.py."""

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration
from .conftest import TEST_API_KEY, TEST_WEBHOOK_ID

from tests.common import MockConfigEntry, snapshot_platform
from tests.typing import ClientSessionGenerator

TEST_DATA = {
    "api_key": TEST_API_KEY,
    "error_code": 0,
    "sensors": [
        {
            "slot": 1,
            "samples": [
                {"t": "2025-01-01 12:00:00", "v": 1.0},
                {"t": "2025-01-01 12:00:05", "v": 1.1},
                {"t": "2025-01-01 12:00:10", "v": 1.2},
            ],
        },
        {
            "slot": 2,
            "samples": [
                {"t": "2025-01-01 12:00:00", "v": 2.0},
                {"t": "2025-01-01 12:00:05", "v": 2.1},
                {"t": "2025-01-01 12:00:10", "v": 2.2},
            ],
        },
        {
            "slot": 3,
            "samples": [
                {"t": "2025-01-01 12:00:00", "v": 3.0},
                {"t": "2025-01-01 12:00:05", "v": 3.1},
                {"t": "2025-01-01 12:00:10", "v": 3.2},
            ],
        },
        {
            "slot": 4,
            "samples": [
                {"t": "2025-01-01 12:00:00", "v": 4.0},
                {"t": "2025-01-01 12:00:05", "v": 4.1},
                {"t": "2025-01-01 12:00:10", "v": 4.2},
            ],
        },
    ],
}


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    hass_client_no_auth: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    mocked_config_entry: MockConfigEntry,
) -> None:
    """Test all entities."""

    with patch("homeassistant.components.vegehub.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mocked_config_entry)

        await hass.async_block_till_done()
        await hass.async_start()
        await hass.async_block_till_done()

        assert TEST_WEBHOOK_ID in hass.data["webhook"], "Webhook was not registered"

        # Verify the webhook handler
        webhook_info = hass.data["webhook"][TEST_WEBHOOK_ID]
        assert webhook_info["handler"], "Webhook handler is not set"

        client = await hass_client_no_auth()
        resp = await client.post(f"/api/webhook/{TEST_WEBHOOK_ID}", json=TEST_DATA)

        # Wait for remaining tasks to complete.
        await hass.async_block_till_done()
        assert resp.status == 200, f"Unexpected status code: {resp.status}"
        await snapshot_platform(
            hass, entity_registry, snapshot, mocked_config_entry.entry_id
        )
