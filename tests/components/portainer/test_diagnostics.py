"""Test the Portainer component diagnostics."""

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.portainer.diagnostics import async_get_device_diagnostics
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_get_config_entry_diagnostics(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test if get_config_entry_diagnostics returns the correct data."""
    await setup_integration(hass, mock_config_entry)

    diagnostics_entry = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )
    assert diagnostics_entry == snapshot(
        exclude=props(
            "created_at",
            "modified_at",
            "repr",
        )
    )


async def test_async_get_device_diagnostics(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device diagnostics include entities and their states."""
    await setup_integration(hass, mock_config_entry)

    ent_reg = er.async_get(hass)
    entity_id = "binary_sensor.practical_morse_status"
    ent = ent_reg.async_get(entity_id)
    assert ent is not None and ent.device_id is not None

    device = device_registry.async_get(ent.device_id)
    assert device is not None

    diagnostics = await async_get_device_diagnostics(hass, mock_config_entry, device)

    assert diagnostics == snapshot(
        exclude=props(
            "modified_at",
            "via_device_id",
            "created_at",
            "id",
            "device_id",
            "last_changed",
            "last_updated",
            "last_reported",
            "repr",
        )
    )
