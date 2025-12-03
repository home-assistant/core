"""Diagnostic tests for Anglian Water."""

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.anglian_water.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_anglian_water_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    await setup_integration(hass, mock_config_entry)

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )


async def test_device_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_anglian_water_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device diagnostics."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device(identifiers={(DOMAIN, "TESTSN")})
    assert device
    assert await get_diagnostics_for_device(
        hass, hass_client, mock_config_entry, device
    ) == snapshot(
        exclude=props(
            "device_entry_id",
            "created_at",
            "modified_at",
        )
    )
