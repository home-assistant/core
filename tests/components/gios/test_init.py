"""Test init of GIOS integration."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.air_quality import DOMAIN as AIR_QUALITY_PLATFORM
from homeassistant.components.gios.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("init_integration")
async def test_async_setup_entry(
    hass: HomeAssistant,
) -> None:
    """Test a successful setup entry."""
    state = hass.states.get("sensor.home_pm2_5")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "4"


async def test_config_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gios: MagicMock,
) -> None:
    """Test for setup failure if connection to GIOS is missing."""
    mock_gios.create.side_effect = ConnectionError()

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("init_integration")
async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful unload of entry."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_migrate_device_and_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mock_gios: MagicMock,
) -> None:
    """Test device_info identifiers and config entry migration."""
    mock_config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id, identifiers={(DOMAIN, 123)}
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    migrated_device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id, identifiers={(DOMAIN, "123")}
    )
    assert device_entry.id == migrated_device_entry.id


async def test_migrate_unique_id_to_str(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gios: MagicMock,
) -> None:
    """Test device_info identifiers and config entry migration."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        unique_id=int(mock_config_entry.unique_id),  # type: ignore[misc]
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.unique_id == "123"


async def test_remove_air_quality_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_gios: MagicMock,
) -> None:
    """Test remove air_quality entities from registry."""
    mock_config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        AIR_QUALITY_PLATFORM,
        DOMAIN,
        "123",
        suggested_object_id="home",
        disabled_by=None,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entry = entity_registry.async_get("air_quality.home")
    assert entry is None
