"""Test init."""

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.niko_home_control.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_migrate_entry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Validate that the unique_id is migrated to the new unique_id."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        minor_version=1,
        unique_id="light_1",
        data={CONF_HOST: "192.168.0.123"},
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    entity_entry = entity_registry.async_get_or_create(
        LIGHT_DOMAIN, DOMAIN, config_entry.unique_id
    )
    assert entity_entry.unique_id != "light_1"
