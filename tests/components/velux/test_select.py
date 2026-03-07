"""Test Velux select entities."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pyvlx.const import Velocity

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_OPTION, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import (
    MockConfigEntry,
    SnapshotAssertion,
    mock_restore_cache,
    snapshot_platform,
)


@pytest.fixture
def platform() -> Platform:
    """Fixture to specify platform to test."""
    return Platform.SELECT


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "setup_integration")
async def test_select_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_pyvlx: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot the entity and validate registry metadata for select entities."""
    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_config_entry.entry_id,
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "setup_integration")
async def test_select_device_association(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_pyvlx: MagicMock,
    mock_window: AsyncMock,
) -> None:
    """Test select device association."""
    entity_id = entity_registry.async_get_entity_id(
        Platform.SELECT, "velux", f"{mock_window.serial_number}_velocity"
    )
    assert entity_id is not None

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.device_id is not None
    device_entry = device_registry.async_get(entity_entry.device_id)
    assert device_entry is not None

    assert ("velux", mock_window.serial_number) in device_entry.identifiers
    assert device_entry.name == mock_window.name


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "setup_integration")
async def test_velocity_select_option(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_pyvlx: MagicMock,
    mock_window: AsyncMock,
) -> None:
    """Test changing the velocity option."""
    entity_id = entity_registry.async_get_entity_id(
        Platform.SELECT, "velux", f"{mock_window.serial_number}_velocity"
    )
    assert entity_id is not None

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {"entity_id": entity_id, ATTR_OPTION: "silent"},
        blocking=True,
    )

    assert mock_window.use_default_velocity is True
    assert mock_window.default_velocity == Velocity.SILENT

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {"entity_id": entity_id, ATTR_OPTION: "fast"},
        blocking=True,
    )

    assert mock_window.use_default_velocity is True
    assert mock_window.default_velocity == Velocity.FAST

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {"entity_id": entity_id, ATTR_OPTION: "default"},
        blocking=True,
    )

    assert mock_window.use_default_velocity is False
    assert mock_window.default_velocity == Velocity.DEFAULT


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_velocity_select_restore(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyvlx: MagicMock,
    mock_window: AsyncMock,
    platform: Platform,
) -> None:
    """Test restoring the velocity option."""
    entity_id = f"select.{mock_window.name.lower().replace(' ', '_')}_velocity"

    # Mock the restore cache before setting up the integration
    mock_restore_cache(hass, [State(entity_id, "silent")])

    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.velux.PLATFORMS", [platform]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Verify that the restored state was pushed to the node
    assert mock_window.use_default_velocity is True
    assert mock_window.default_velocity == Velocity.SILENT

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "silent"
