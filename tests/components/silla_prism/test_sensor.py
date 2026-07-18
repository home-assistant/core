"""Test the Silla Prism sensors."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import fire_burst, setup_integration

from tests.common import MockConfigEntry, snapshot_platform
from tests.typing import MqttMockHAClient


async def test_sensors(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensors, including the milliamp-to-amp conversion."""
    await setup_integration(hass, mock_config_entry)
    await fire_burst(hass)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
