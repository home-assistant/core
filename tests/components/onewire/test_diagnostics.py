"""Test 1-Wire diagnostics."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.onewire import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_owproxy_mock_devices

from tests.common import MockConfigEntry
from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.onewire._PLATFORMS", [Platform.SWITCH]):
        yield


@pytest.mark.parametrize("device_id", ["EF.111111111113"], indirect=True)
async def test_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    owproxy: MagicMock,
    device_id: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    setup_owproxy_mock_devices(owproxy, [device_id])
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == snapshot
    )


@pytest.mark.parametrize("device_id", ["EF.111111111113"], indirect=True)
async def test_device_diagnostics(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    hass_client: ClientSessionGenerator,
    owproxy: MagicMock,
    device_id: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device diagnostics."""
    setup_owproxy_mock_devices(owproxy, [device_id])
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, "EF.111111111113")})
    assert device is not None

    assert (
        await get_diagnostics_for_device(hass, hass_client, config_entry, device)
        == snapshot
    )
