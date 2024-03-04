"""Test ViCare device info."""

from unittest.mock import MagicMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.vicare.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr


def test_device_info(
    hass: HomeAssistant,
    mock_vicare_gas_boiler: MagicMock,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test a device."""
    assert device_registry.async_get_device({(DOMAIN, "gateway0")}) == snapshot
