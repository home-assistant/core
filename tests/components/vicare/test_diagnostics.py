"""Test ViCare diagnostics."""

from unittest.mock import MagicMock

from PyViCare.PyViCareUtils import PyViCareDeviceCommunicationError
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_vicare_gas_boiler: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    diag = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_vicare_gas_boiler
    )

    assert diag == snapshot(exclude=props("created_at", "modified_at"))


async def test_diagnostics_with_offline_device(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_vicare_gas_boiler: MagicMock,
) -> None:
    """Test that an offline gateway on one device does not abort diagnostics."""
    config_entry = hass.config_entries.async_entries("vicare")[0]
    devices = config_entry.runtime_data.client.all_devices

    # Force the first device to fail with GATEWAY_OFFLINE; the rest must still dump.
    devices[0].dump_secure = MagicMock(
        side_effect=PyViCareDeviceCommunicationError(
            {"extendedPayload": {"reason": "GATEWAY_OFFLINE"}}
        )
    )

    diag = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_vicare_gas_boiler
    )

    assert len(diag["data"]) == len(devices)
    error_entry = diag["data"][0]
    assert "error" in error_entry
    assert "GATEWAY_OFFLINE" in error_entry["error"]
    assert error_entry["device"]["id"] == devices[0].device_id
