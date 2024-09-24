"""Tests for the diagnostics data provided by the Zeversolar integration."""

from syrupy import SnapshotAssertion

from homeassistant.components.zeversolar import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import MOCK_SERIAL_NUMBER, init_integration

from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""

    entry = await init_integration(hass)

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot


async def test_device_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device diagnostics."""

    entry = await init_integration(hass)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_SERIAL_NUMBER)}
    )

    assert (
        await get_diagnostics_for_device(hass, hass_client, entry, device) == snapshot
    )
