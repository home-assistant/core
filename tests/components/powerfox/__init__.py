"""Tests for the Powerfox integration."""

from datetime import UTC, datetime

from powerfox import Device, DeviceType

from homeassistant.components.powerfox.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_DIRECT_HOST = "1.1.1.1"


def create_mock_device(device_type: DeviceType) -> Device:
    """Return a mocked Powerfox device."""
    return Device(
        id="device-id",
        date_added=datetime(2024, 1, 1, tzinfo=UTC),
        main_device=True,
        bidirectional=False,
        type=device_type,
        name="Powerfox Device",
    )


def create_empty_config_entry() -> MockConfigEntry:
    """Return a minimal config entry for coordinator tests."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.runtime_data = []
    return entry


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the integration."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
