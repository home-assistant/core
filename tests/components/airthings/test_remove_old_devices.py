"""Test Airthings devices, and ensure old devices are removed."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import MockAirthings, setup_integration
from .const import TEST_DATA, THREE_DEVICES, TWO_DEVICES


async def test_remove_old_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that old devices are removed when new data is fetched."""

    # Use MockAirthings instead of real Airthings for testing
    with patch(
        "homeassistant.components.airthings.Airthings",
        return_value=MockAirthings(THREE_DEVICES),
    ):
        entry = await setup_integration(hass)

    assert entry is not None
    assert entry.domain == "airthings"
    assert entry.data == TEST_DATA

    assert len(device_registry.devices) == len(THREE_DEVICES)

    with patch(
        "homeassistant.components.airthings.Airthings",
        return_value=MockAirthings(TWO_DEVICES),
    ):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert len(device_registry.devices) == len(TWO_DEVICES)
