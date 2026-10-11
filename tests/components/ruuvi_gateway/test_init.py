"""Test the Ruuvi Gateway setup."""

from homeassistant.components.bluetooth import DOMAIN as BLUETOOTH_DOMAIN
from homeassistant.components.ruuvi_gateway.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .consts import BASE_DATA, EXPECTED_TITLE, GATEWAY_MAC, GATEWAY_MAC_LOWER

from tests.common import MockConfigEntry


async def test_scanner_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the scanner gets a device entry that can hold an area."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=GATEWAY_MAC_LOWER,
        title=EXPECTED_TITLE,
        data=BASE_DATA,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    scanner_entry = hass.config_entries.async_entry_for_domain_unique_id(
        BLUETOOTH_DOMAIN, GATEWAY_MAC
    )
    assert scanner_entry is not None

    device_entry = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_BLUETOOTH, GATEWAY_MAC), scanner_entry.entry_id
    )
    assert device_entry is not None


async def test_scanner_removed_with_entry(
    hass: HomeAssistant,
) -> None:
    """Test removing the entry also removes the scanner's Bluetooth entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=GATEWAY_MAC_LOWER,
        title=EXPECTED_TITLE,
        data=BASE_DATA,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (
        hass.config_entries.async_entry_for_domain_unique_id(
            BLUETOOTH_DOMAIN, GATEWAY_MAC
        )
        is not None
    )

    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert (
        hass.config_entries.async_entry_for_domain_unique_id(
            BLUETOOTH_DOMAIN, GATEWAY_MAC
        )
        is None
    )
