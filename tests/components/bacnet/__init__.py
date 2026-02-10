"""Tests for the BACnet integration."""

from homeassistant.components.bacnet.const import (
    CONF_DEVICE_ADDRESS,
    CONF_DEVICE_ID,
    CONF_DEVICE_INSTANCE,
    CONF_DEVICES,
    CONF_INTERFACE,
    CONF_SELECTED_OBJECTS,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_DEVICE_ID = 1234
MOCK_DEVICE_KEY = str(MOCK_DEVICE_ID)
MOCK_DEVICE_ADDRESS = "192.168.1.100:47808"
MOCK_DEVICE_INSTANCE = 3_500_000
MOCK_LISTEN_ADDRESS = "eth0"  # Interface name, not IP


def create_mock_hub_config_entry(
    selected_objects: list[str] | None = None,
) -> MockConfigEntry:
    """Create a mock hub config entry with a device for testing."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=3,
        title=f"BACnet Client ({MOCK_LISTEN_ADDRESS})",
        data={
            CONF_INTERFACE: MOCK_LISTEN_ADDRESS,
            CONF_DEVICE_INSTANCE: MOCK_DEVICE_INSTANCE,
            CONF_DEVICES: {
                MOCK_DEVICE_KEY: {
                    CONF_DEVICE_ID: MOCK_DEVICE_ID,
                    CONF_DEVICE_ADDRESS: MOCK_DEVICE_ADDRESS,
                    CONF_SELECTED_OBJECTS: selected_objects or [],
                },
            },
        },
    )


def create_mock_hub_only_config_entry() -> MockConfigEntry:
    """Create a mock hub config entry with no devices."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=3,
        title=f"BACnet Client ({MOCK_LISTEN_ADDRESS})",
        data={
            CONF_INTERFACE: MOCK_LISTEN_ADDRESS,
            CONF_DEVICE_INSTANCE: MOCK_DEVICE_INSTANCE,
            CONF_DEVICES: {},
        },
    )


async def init_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the BACnet integration with a hub and one device."""
    entry = create_mock_hub_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # The first coordinator refresh uses quick mode (no values polled).
    # Trigger a second refresh so presentValue gets polled for all objects.
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]
    coordinator._initial_setup_done = True
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    return entry
