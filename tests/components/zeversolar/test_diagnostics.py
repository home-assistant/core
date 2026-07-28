"""Tests for the diagnostics data provided by the Zeversolar integration."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.zeversolar.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import MOCK_SERIAL_NUMBER

from tests.common import MockConfigEntry
from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    init_integration: MockConfigEntry,
) -> None:
    """Test config entry diagnostics."""
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
        == snapshot
    )


async def test_device_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    init_integration: MockConfigEntry,
) -> None:
    """Test device diagnostics."""
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_SERIAL_NUMBER)}
    )

    assert (
        await get_diagnostics_for_device(hass, hass_client, init_integration, device)
        == snapshot
    )
