"""Test Airthings devices, and ensure old devices are removed."""

from unittest.mock import patch

from homeassistant.components.airthings import DOMAIN
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import TEST_DATA

from tests.common import MockConfigEntry


async def test_remove_old_devices(hass: HomeAssistant) -> None:
    """Test that old devices are removed when new data is fetched."""

    first_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_DATA,
        unique_id=TEST_DATA[CONF_ID],
    )
    first_entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)

    device_registry.async_get_or_create(
        config_entry_id=first_entry.entry_id,
        identifiers={(DOMAIN, "device_1")},
        name="Device 1",
    )
    assert (
        device_registry.async_get_device(identifiers={(DOMAIN, "device_1")}) is not None
    )

    # Fetch new data with no devices
    with patch(
        "homeassistant.components.airthings.coordinator.AirthingsDataUpdateCoordinator._update_method",
        return_value={},
    ):
        await hass.config_entries.async_setup(first_entry.entry_id)
        await hass.async_block_till_done()

    # Check that the old device is removed
    assert not device_registry.async_get_device(identifiers={(DOMAIN, "device_1")})
