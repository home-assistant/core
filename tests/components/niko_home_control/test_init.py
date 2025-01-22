"""Test init."""

from unittest.mock import AsyncMock

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.niko_home_control.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_migrate_entry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_setup_entry: AsyncMock
) -> None:
    """Validate that the unique_id is migrated to the new unique_id."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        minor_version=1,
        data={CONF_HOST: "192.168.0.123"},
    )
    config_entry.add_to_hass(hass)
    entity_entry = entity_registry.async_get_or_create(
        LIGHT_DOMAIN, DOMAIN, "light-1", config_entry=config_entry
    )
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get(entity_entry.entity_id)

    assert config_entry.minor_version == 2
    assert (
        entity_registry.async_get(entity_entry.entity_id).unique_id
        == f"{config_entry.entry_id}-1"
    )
