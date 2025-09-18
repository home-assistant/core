"""Tests for the diagnostics module."""

from unittest.mock import MagicMock

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from .conftest import init_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    eheimdigital_hub_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry diagnostics."""

    await init_integration(hass, mock_config_entry)

    for device in eheimdigital_hub_mock.return_value.devices.values():
        await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
            device.mac_address, device.device_type
        )

    mock_config_entry.runtime_data.data = eheimdigital_hub_mock.return_value.devices

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result == snapshot(exclude=props("created_at", "modified_at", "entry_id"))
