"""Tests for the Watergate event entity platform."""

from collections.abc import Generator

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import StateType

from . import init_integration
from .const import MOCK_WEBHOOK_ID

from tests.common import AsyncMock, MockConfigEntry, patch, snapshot_platform
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_event(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_entry: MockConfigEntry,
    mock_watergate_client: Generator[AsyncMock],
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test states of the sensor."""
    freezer.move_to("2021-01-09 12:00:00+00:00")
    with patch("homeassistant.components.watergate.PLATFORMS", [Platform.EVENT]):
        await init_integration(hass, mock_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "event_type"),
    [
        ("sonic_volume_auto_shut_off", "volume_threshold"),
        ("sonic_duration_auto_shut_off", "duration_threshold"),
    ],
)
async def test_auto_shut_off_webhook(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_entry: MockConfigEntry,
    mock_watergate_client: Generator[AsyncMock],
    entity_id: str,
    event_type: str,
) -> None:
    """Test if water flow webhook is handled correctly."""
    await init_integration(hass, mock_entry)

    def assert_state(entity_id: str, expected_state: str):
        state = hass.states.get(f"event.{entity_id}")
        assert state.state == str(expected_state)

    assert_state(entity_id, "unknown")

    telemetry_change_data = {
        "type": "auto-shut-off-report",
        "data": {
            "type": event_type,
            "volume": 1500,
            "duration": 30,
            "timestamp": 1730148016,
        },
    }
    client = await hass_client_no_auth()
    await client.post(f"/api/webhook/{MOCK_WEBHOOK_ID}", json=telemetry_change_data)

    await hass.async_block_till_done()

    def assert_extra_state(
        entity_id: str, attribute: str, expected_attribute: StateType
    ):
        attributes = hass.states.get(f"event.{entity_id}").attributes
        assert attributes.get(attribute) == expected_attribute

    assert_extra_state(entity_id, "event_type", event_type)
    assert_extra_state(entity_id, "volume", 1500)
    assert_extra_state(entity_id, "duration", 30)
