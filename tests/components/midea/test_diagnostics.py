"""Tests for midea_lan diagnostics.py."""

from collections.abc import Callable

from midealocal.const import DeviceType
from midealocal.devices.ac import DeviceAttributes as ACAttributes
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import DummyDevice

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    device = DummyDevice(
        DeviceType.AC,
        attributes={
            ACAttributes.power: True,
            ACAttributes.mode: 1,
            ACAttributes.target_temperature: 22.0,
            ACAttributes.indoor_temperature: 21.0,
            ACAttributes.fan_speed: 103,
            ACAttributes.swing_vertical: True,
            ACAttributes.swing_horizontal: True,
            ACAttributes.min_temperature: 17,
            ACAttributes.max_temperature: 26,
        },
    )
    config_entry = mock_config_entry(device)
    await setup_integration(hass, config_entry, device)

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert result == snapshot(
        exclude=props("created_at", "modified_at", "entry_id", "last_activity")
    )
