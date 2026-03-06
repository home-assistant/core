"""Test the Casper Glow integration init."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.bluetooth import BluetoothChange
from homeassistant.components.casper_glow.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from . import CASPER_GLOW_DISCOVERY_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_async_setup_entry_success(hass: HomeAssistant) -> None:
    """Test successful setup of a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Jar",
        data={CONF_ADDRESS: CASPER_GLOW_DISCOVERY_INFO.address},
        unique_id=CASPER_GLOW_DISCOVERY_INFO.address,
    )
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, CASPER_GLOW_DISCOVERY_INFO)

    with patch(
        "pycasperglow.CasperGlow.query_state",
        new_callable=AsyncMock,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not None
    assert entry.runtime_data.device is not None


async def test_async_setup_entry_device_not_found(hass: HomeAssistant) -> None:
    """Test setup raises ConfigEntryNotReady when BLE device is not found."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Jar",
        data={CONF_ADDRESS: CASPER_GLOW_DISCOVERY_INFO.address},
        unique_id=CASPER_GLOW_DISCOVERY_INFO.address,
    )
    entry.add_to_hass(hass)

    # Do not inject BLE info — device is not in the cache
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_async_unload_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test unloading a config entry."""
    result = await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert result is True
    assert config_entry.state == ConfigEntryState.NOT_LOADED


async def test_ble_device_update_callback(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that BLE device updates are forwarded to the CasperGlow instance."""
    coordinator = config_entry.runtime_data
    device = coordinator.device

    with patch.object(device, "set_ble_device") as mock_set_ble:
        # Directly call the coordinator's BLE event handler to verify it
        # forwards the updated BLE device to the CasperGlow instance.
        coordinator._async_handle_bluetooth_event(
            CASPER_GLOW_DISCOVERY_INFO, BluetoothChange.ADVERTISEMENT
        )

        mock_set_ble.assert_called_once()
        assert (
            mock_set_ble.call_args[0][0].address == CASPER_GLOW_DISCOVERY_INFO.address
        )


async def test_coordinator_polls_on_advertisement(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that the coordinator polls device state when an advertisement is received."""
    # Reload the entry with a fresh query_state mock so we can count exactly how
    # many polls the coordinator fires when an advertisement is received at startup.
    with patch(
        "pycasperglow.CasperGlow.query_state",
        new_callable=AsyncMock,
    ) as mock_query_state:
        await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert config_entry.state is ConfigEntryState.LOADED
    mock_query_state.assert_called_once()
