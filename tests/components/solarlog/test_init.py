"""Test the initialization."""

from homeassistant.components.solarlog.const import DOMAIN
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from .test_config_flow import HOST, NAME

from tests.common import MockConfigEntry


async def test_migrate_config_entry(
    hass: HomeAssistant, device_reg: DeviceRegistry, entity_reg: EntityRegistry
) -> None:
    """Test successful migration of entry data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=NAME,
        data={
            CONF_HOST: HOST,
        },
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    device = device_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="Solar-Log",
        name="solarlog",
    )
    sensor_entity = entity_reg.async_get_or_create(
        config_entry=entry,
        platform=DOMAIN,
        domain=Platform.SENSOR,
        unique_id=f"{entry.entry_id}_time",
        device_id=device.id,
    )

    assert entry.version == 1
    assert entry.minor_version == 1
    assert sensor_entity.unique_id == f"{entry.entry_id}_time"

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_migrated = entity_reg.async_get(sensor_entity.entity_id)
    assert entity_migrated
    assert entity_migrated.unique_id == f"{entry.entry_id}_last_updated"

    assert entry.version == 1
    assert entry.minor_version == 2
    assert entry.data[CONF_HOST] == HOST
    assert entry.data["extended_data"] is False
