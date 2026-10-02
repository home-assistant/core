"""Test the Govee BLE init."""

from unittest.mock import patch

import pytest

from homeassistant.components.bluetooth import BluetoothScanningMode
from homeassistant.components.govee_ble.const import CONF_DEVICE_TYPE, DOMAIN
from homeassistant.components.govee_ble.coordinator import ACTIVE_SCAN_DURATION
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("device_type", "expected_mode", "expected_scan_duration"),
    [
        pytest.param(
            "H5074",
            BluetoothScanningMode.ACTIVE,
            ACTIVE_SCAN_DURATION,
            id="h5074_scan_response",
        ),
        pytest.param(
            "H5075",
            BluetoothScanningMode.ACTIVE,
            ACTIVE_SCAN_DURATION,
            id="h5075_scan_response",
        ),
        pytest.param(
            "H5179",
            BluetoothScanningMode.PASSIVE,
            None,
            id="primary_advertisement",
        ),
    ],
)
async def test_active_scan_duration(
    hass: HomeAssistant,
    device_type: str,
    expected_mode: BluetoothScanningMode,
    expected_scan_duration: float | None,
) -> None:
    """Test only scan-response-only models are scanned actively."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="61DE521B-F0BF-9F44-64D4-75BBE1738105",
        data={CONF_DEVICE_TYPE: device_type},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback"
    ) as mock_register_callback:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert mock_register_callback.call_args.args[3] == expected_mode
    assert (
        mock_register_callback.call_args.kwargs["scan_duration"]
        == expected_scan_duration
    )
