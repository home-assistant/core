"""Tests for the Bond cover device."""
import logging

from bond import Bond

from homeassistant.components.bond.utils import get_bond_devices
from homeassistant.core import HomeAssistant

from tests.async_mock import patch

_LOGGER = logging.getLogger(__name__)


async def test_get_bond_devices(hass: HomeAssistant):
    """Tests that the querying for devices delegates to API."""
    bond: Bond = Bond("1.1.1.1", "test-token")

    with patch(
        "bond.Bond.getDeviceIds", return_value=["device-1", "device-2"],
    ) as mock_get_device_ids, patch("bond.Bond.getDevice") as mock_get_device:
        await get_bond_devices(hass, bond)

    assert len(mock_get_device_ids.mock_calls) == 1
    assert len(mock_get_device.mock_calls) == 2
