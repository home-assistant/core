"""Test sensors."""

from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.monarch_money.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_config_api: AsyncMock,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.monarch_money.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_value_account_keeps_legacy_balance_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_config_api: AsyncMock,
) -> None:
    """Test real-estate accounts keep their legacy balance entity and new value entity."""
    legacy_unique_id = f"{mock_config_entry.unique_id}_90000000020_balance"
    value_unique_id = f"{mock_config_entry.unique_id}_90000000020_value"

    mock_config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        legacy_unique_id,
        config_entry=mock_config_entry,
    )

    with patch("homeassistant.components.monarch_money.PLATFORMS", [Platform.SENSOR]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert entity_registry.async_get_entity_id("sensor", DOMAIN, legacy_unique_id)
    assert entity_registry.async_get_entity_id("sensor", DOMAIN, value_unique_id)
