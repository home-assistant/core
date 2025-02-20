"""Unit tests for the VegeHub integration's sensor.py."""

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import (
    CONF_DEVICE,
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_MAC,
    CONF_WEBHOOK_ID,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, snapshot_platform

TEST_IP = "192.168.0.100"
TEST_SIMPLE_MAC = "A1B2C3D4E5F6"
TEST_HOSTNAME = "VegeHub"
TEST_WEBHOOK_ID = "webhook_id"
HUB_DATA = {
    "first_boot": False,
    "page_updated": False,
    "error_message": 0,
    "num_channels": 2,
    "num_actuators": 2,
    "version": "3.4.5",
    "agenda": 1,
    "batt_v": 9.0,
    "num_vsens": 0,
    "is_ac": 0,
    "has_sd": 0,
    "on_ap": 0,
}


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    config_entry = MockConfigEntry(
        domain="vegehub",
        data={
            CONF_MAC: TEST_SIMPLE_MAC,
            CONF_IP_ADDRESS: TEST_IP,
            CONF_HOST: TEST_HOSTNAME,
            CONF_DEVICE: HUB_DATA,
            CONF_WEBHOOK_ID: TEST_WEBHOOK_ID,
        },
        unique_id=TEST_SIMPLE_MAC,
    )
    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.vegehub.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)
