"""Test the initialization."""

from unittest.mock import AsyncMock

from solarlog_cli.solarlog_exceptions import SolarLogConnectionError

from homeassistant.components.solarlog.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from . import setup_platform
from .const import HOST, NAME

from tests.common import MockConfigEntry


async def test_load_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_solarlog_connector: AsyncMock,
) -> None:
    """Test load and unload."""

    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_raise_config_entry_not_ready_when_offline(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_solarlog_connector: AsyncMock,
) -> None:
    """Config entry state is SETUP_RETRY when Solarlog is offline."""

    mock_solarlog_connector.update_data.side_effect = SolarLogConnectionError

    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    assert len(hass.config_entries.flow.async_progress()) == 0


async def test_migrate_config_entry(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    entity_registry: EntityRegistry,
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

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="Solar-Log",
        name="solarlog",
    )
    sensor_entity = entity_registry.async_get_or_create(
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

    entity_migrated = entity_registry.async_get(sensor_entity.entity_id)
    assert entity_migrated
    assert entity_migrated.unique_id == f"{entry.entry_id}_last_updated"

    assert entry.version == 1
    assert entry.minor_version == 2
    assert entry.data[CONF_HOST] == HOST
    assert entry.data["extended_data"] is False
