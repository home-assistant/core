"""Test Traccar Server diagnostics."""
from collections.abc import Generator
from unittest.mock import AsyncMock

from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .common import setup_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_traccar_api_client: Generator[AsyncMock, None, None],
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    await setup_integration(hass, mock_config_entry)

    result = await get_diagnostics_for_config_entry(
        hass,
        hass_client,
        mock_config_entry,
    )

    assert result == snapshot(name="entry")


async def test_device_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_traccar_api_client: Generator[AsyncMock, None, None],
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device diagnostics."""
    await setup_integration(hass, mock_config_entry)

    devices = dr.async_entries_for_config_entry(
        hass.helpers.device_registry.async_get(hass),
        mock_config_entry.entry_id,
    )

    assert len(devices) == 1

    for device in dr.async_entries_for_config_entry(
        hass.helpers.device_registry.async_get(hass), mock_config_entry.entry_id
    ):
        result = await get_diagnostics_for_device(
            hass, hass_client, mock_config_entry, device=device
        )

        assert result == snapshot(name=device.name)
