"""Tests for the BACnet integration."""

from homeassistant.components.bacnet.const import (
    CONF_DEVICE_ADDRESS,
    CONF_DEVICE_ID,
    CONF_ENTRY_TYPE,
    CONF_HUB_ID,
    CONF_INTERFACE,
    DOMAIN,
    ENTRY_TYPE_DEVICE,
    ENTRY_TYPE_HUB,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_DEVICE_ID = 1234
MOCK_DEVICE_ADDRESS = "192.168.1.100:47808"
MOCK_LISTEN_ADDRESS = "eth0"  # Interface name, not IP


def create_mock_hub_config_entry() -> MockConfigEntry:
    """Create a mock hub config entry for testing."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=2,
        title=f"BACnet Client ({MOCK_LISTEN_ADDRESS})",
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_HUB,
            CONF_INTERFACE: MOCK_LISTEN_ADDRESS,
        },
    )


def create_mock_device_config_entry(hub_entry_id: str | None = None) -> MockConfigEntry:
    """Create a mock device config entry for testing."""
    data = {
        CONF_ENTRY_TYPE: ENTRY_TYPE_DEVICE,
        CONF_DEVICE_ID: MOCK_DEVICE_ID,
        CONF_DEVICE_ADDRESS: MOCK_DEVICE_ADDRESS,
    }
    if hub_entry_id:
        data[CONF_HUB_ID] = hub_entry_id

    return MockConfigEntry(
        domain=DOMAIN,
        version=2,
        title="Test HVAC Controller",
        unique_id=str(MOCK_DEVICE_ID),
        data=data,
    )


def create_mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry for testing."""
    return create_mock_device_config_entry()


async def _setup_hub_and_device(
    hass: HomeAssistant,
) -> tuple[MockConfigEntry, MockConfigEntry]:
    """Set up hub and device entries with a coordinator refresh to poll values."""
    # Create and set up hub first
    hub_entry = create_mock_hub_config_entry()
    hub_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    # Create and set up device
    device_entry = create_mock_device_config_entry(hub_entry.entry_id)
    device_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(device_entry.entry_id)
    await hass.async_block_till_done()

    # The first coordinator refresh uses quick mode (no values polled).
    # Trigger a second refresh so presentValue gets polled for all objects.
    coordinator = device_entry.runtime_data.coordinator
    coordinator._initial_setup_done = True
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    return hub_entry, device_entry


async def init_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the BACnet integration in Home Assistant with hub model."""
    _, device_entry = await _setup_hub_and_device(hass)
    return device_entry


async def init_integration_with_hub(
    hass: HomeAssistant,
) -> tuple[MockConfigEntry, MockConfigEntry]:
    """Set up the BACnet integration with hub model."""
    return await _setup_hub_and_device(hass)
