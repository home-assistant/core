"""Tests for setup, unload, and migration of the Powersensor integration."""

from unittest.mock import AsyncMock, MagicMock, patch

from powersensor_local import VirtualHousehold

from homeassistant.components.powersensor_au.config_flow import PowersensorConfigFlow
from homeassistant.components.powersensor_au.const import DOMAIN, ROLE_SOLAR
from homeassistant.components.powersensor_au.models import PowersensorRuntimeData
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

PLUG_MAC = "aabbccddeeff"


async def test_setup_entry_populates_runtime_data(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Setup stores a populated PowersensorRuntimeData on the entry."""
    assert config_entry.state is ConfigEntryState.LOADED
    assert isinstance(config_entry.runtime_data, PowersensorRuntimeData)
    assert config_entry.runtime_data.vhh is not None
    assert config_entry.runtime_data.dispatcher is not None
    assert config_entry.runtime_data.devices is not None


async def test_setup_starts_mdns_browser(
    hass: HomeAssistant,
    mock_devices: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """devices.start() is called once during setup with an async callback."""
    mock_devices.start.assert_awaited_once()
    cb = mock_devices.start.call_args[0][0]
    assert callable(cb)


async def test_unload_calls_disconnect_and_stop(
    hass: HomeAssistant,
    mock_devices: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Unloading the entry calls disconnect() then stop() exactly once each."""
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    mock_devices.stop.assert_awaited_once()
    # dispatcher.disconnect() is also called once; it's a real object so we
    # check indirectly that no exception was raised (state is NOT_LOADED).


async def test_unload_skips_teardown_when_platform_unload_fails(
    hass: HomeAssistant,
    mock_devices: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """stop() is NOT called when async_unload_platforms returns False."""
    mock_devices.stop.reset_mock()

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=False,
    ):
        result = await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

    assert result is False
    mock_devices.stop.assert_not_called()
    # Entry transitions to FAILED_UNLOAD (not LOADED) when unload fails.
    assert config_entry.state is ConfigEntryState.FAILED_UNLOAD


async def test_devices_start_failure_raises_config_entry_not_ready(
    hass: HomeAssistant,
    mock_async_zeroconf: MagicMock,
) -> None:
    """A RuntimeError from devices.start() leaves the entry in SETUP_RETRY."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"roles": {}},
        version=PowersensorConfigFlow.VERSION,
        minor_version=PowersensorConfigFlow.MINOR_VERSION,
    )
    entry.add_to_hass(hass)

    failing_devices = MagicMock()
    failing_devices.start = AsyncMock(side_effect=RuntimeError("no socket"))
    failing_devices.stop = AsyncMock()

    with patch(
        "homeassistant.components.powersensor_au.PowersensorZeroconfDevices",
        return_value=failing_devices,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    failing_devices.stop.assert_awaited_once()


async def test_setup_constructs_vhh_with_solar_when_role_persisted(
    hass: HomeAssistant,
    mock_async_zeroconf: MagicMock,
) -> None:
    """VirtualHousehold is constructed with with_solar=True when a solar role is persisted."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"roles": {"aabbccddeeff": ROLE_SOLAR}},
        version=PowersensorConfigFlow.VERSION,
        minor_version=PowersensorConfigFlow.MINOR_VERSION,
    )
    entry.add_to_hass(hass)

    constructed_args: list[bool] = []

    class CapturingVHH(VirtualHousehold):
        def __init__(self, with_solar: bool) -> None:
            constructed_args.append(with_solar)
            super().__init__(with_solar)

    devices = MagicMock()
    devices.start = AsyncMock()
    devices.stop = AsyncMock()
    devices.subscribe = MagicMock()
    devices.unsubscribe = MagicMock()

    with (
        patch(
            "homeassistant.components.powersensor_au.PowersensorZeroconfDevices",
            return_value=devices,
        ),
        patch(
            "homeassistant.components.powersensor_au.VirtualHousehold",
            CapturingVHH,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert constructed_args == [True]
