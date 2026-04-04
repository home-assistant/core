"""Test the Eve Online sensor platform."""

from unittest.mock import AsyncMock

from eveonline.models import SkillQueueEntry, WalletBalance
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


async def test_sensor_entity_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
    init_integration: MockConfigEntry,
) -> None:
    """Test that all sensor entities are created with the correct state."""
    for entity_entry in er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    ):
        if entity_entry.disabled_by is not None:
            entity_registry.async_update_entity(
                entity_entry.entity_id, disabled_by=None
            )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("sensor_entity_id", "expected_state"),
    [
        ("sensor.test_capsuleer_wallet_balance", "1234567.89"),
        ("sensor.test_capsuleer_skill_queue", "2"),
    ],
)
async def test_sensor_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
    sensor_entity_id: str,
    expected_state: str,
) -> None:
    """Test that sensors report correct values with specific return data."""
    mock_eveonline_client.async_get_wallet_balance.return_value = WalletBalance(
        balance=1234567.89
    )
    mock_eveonline_client.async_get_skill_queue.return_value = [
        SkillQueueEntry(
            skill_id=3436,
            finished_level=5,
            queue_position=0,
            start_date=None,
            finish_date=None,
        ),
        SkillQueueEntry(
            skill_id=3437,
            finished_level=4,
            queue_position=1,
            start_date=None,
            finish_date=None,
        ),
    ]

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(sensor_entity_id)
    assert state is not None
    assert state.state == expected_state


async def test_unavailable_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test that sensors with no data show as unknown."""
    mock_eveonline_client.async_get_wallet_balance.return_value = None

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_capsuleer_wallet_balance")
    assert state is not None
    assert state.state == "unknown"
