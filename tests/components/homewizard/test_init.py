"""Tests for the homewizard component."""

from unittest.mock import MagicMock

from homewizard_energy.errors import DisabledError
import pytest

from homeassistant.components.homewizard.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_load_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: MagicMock,
) -> None:
    """Test loading and unloading of integration."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(mock_homewizardenergy.device.mock_calls) == 1

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_load_failed_host_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: MagicMock,
) -> None:
    """Test setup handles unreachable host."""
    mock_homewizardenergy.device.side_effect = TimeoutError()
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_load_detect_api_disabled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: MagicMock,
) -> None:
    """Test setup detects disabled API."""
    mock_homewizardenergy.device.side_effect = DisabledError()
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == mock_config_entry.entry_id


@pytest.mark.usefixtures("mock_homewizardenergy")
async def test_load_removes_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup removes reauth flow when API is enabled."""
    mock_config_entry.add_to_hass(hass)

    # Add reauth flow from 'previously' failed init
    mock_config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Flow should be removed
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 0


@pytest.mark.parametrize(
    ("device_fixture", "old_unique_id", "new_unique_id"),
    [
        (
            "HWE-P1",
            "homewizard_G001",
            "homewizard_gas_meter_G001",
        ),
        (
            "HWE-P1",
            "homewizard_W001",
            "homewizard_water_meter_W001",
        ),
        (
            "HWE-P1",
            "homewizard_WW001",
            "homewizard_warm_water_meter_WW001",
        ),
        (
            "HWE-P1",
            "homewizard_H001",
            "homewizard_heat_meter_H001",
        ),
        (
            "HWE-P1",
            "homewizard_IH001",
            "homewizard_inlet_heat_meter_IH001",
        ),
    ],
)
@pytest.mark.usefixtures("mock_homewizardenergy")
async def test_external_sensor_migration(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    old_unique_id: str,
    new_unique_id: str,
) -> None:
    """Test unique ID or External sensors are migrated."""
    mock_config_entry.add_to_hass(hass)

    entity: er.RegistryEntry = entity_registry.async_get_or_create(
        domain=Platform.SENSOR,
        platform=DOMAIN,
        unique_id=old_unique_id,
        config_entry=mock_config_entry,
    )

    assert entity.unique_id == old_unique_id

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_migrated = entity_registry.async_get(entity.entity_id)
    assert entity_migrated
    assert entity_migrated.unique_id == new_unique_id
    assert entity_migrated.previous_unique_id == old_unique_id
