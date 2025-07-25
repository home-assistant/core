"""Unit tests for the VegeHub integration's sensor.py."""

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration
from .conftest import TEST_SIMPLE_MAC, TEST_WEBHOOK_ID

from tests.common import MockConfigEntry, snapshot_platform
from tests.typing import ClientSessionGenerator

UPDATE_DATA = {
    "api_key": "",
    "mac": TEST_SIMPLE_MAC,
    "error_code": 0,
    "sensors": [
        {"slot": 1, "samples": [{"v": 1.5, "t": "2025-01-15T16:51:23Z"}]},
        {"slot": 2, "samples": [{"v": 1.45599997, "t": "2025-01-15T16:51:23Z"}]},
        {"slot": 3, "samples": [{"v": 1.330000043, "t": "2025-01-15T16:51:23Z"}]},
        {"slot": 4, "samples": [{"v": 0.075999998, "t": "2025-01-15T16:51:23Z"}]},
        {"slot": 5, "samples": [{"v": 9.314800262, "t": "2025-01-15T16:51:23Z"}]},
    ],
    "send_time": 1736959883,
    "wifi_str": -27,
}


async def test_sensor_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    hass_client_no_auth: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    mocked_config_entry: MockConfigEntry,
) -> None:
    """Test all entities."""

    with patch("homeassistant.components.vegehub.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mocked_config_entry)

    assert TEST_WEBHOOK_ID in hass.data["webhook"], "Webhook was not registered"

    # Verify the webhook handler
    webhook_info = hass.data["webhook"][TEST_WEBHOOK_ID]
    assert webhook_info["handler"], "Webhook handler is not set"

    client = await hass_client_no_auth()
    resp = await client.post(f"/api/webhook/{TEST_WEBHOOK_ID}", json=UPDATE_DATA)

    # Send the same update again so that the coordinator modifies existing data
    # instead of creating new data.
    resp = await client.post(f"/api/webhook/{TEST_WEBHOOK_ID}", json=UPDATE_DATA)

    # Wait for remaining tasks to complete.
    await hass.async_block_till_done()
    assert resp.status == 200, f"Unexpected status code: {resp.status}"
    await snapshot_platform(
        hass, entity_registry, snapshot, mocked_config_entry.entry_id
    )
