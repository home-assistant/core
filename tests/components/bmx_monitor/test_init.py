"""Tests for setting up a BM2 monitor from an existing config entry."""

from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, patch

from bmx_ble import BM2Generation
from bmx_ble.battery import Battery
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components import bmx_monitor as integration
from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bmx_monitor.const import CONF_BATTERY_TYPE, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.exceptions import ConfigEntryError

pytestmark = pytest.mark.usefixtures("mock_bluetooth")

ADDRESS = "AA:BB:CC:DD:EE:FF"


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a previously configured monitor."""
    config_entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS)
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.mark.parametrize("validation", ["valid_passive", "valid_active"])
async def test_setup_from_cached_advertisement(
    hass: HomeAssistant, entry: MockConfigEntry, validation: str
) -> None:
    """Both passive and active validation allow the BLE processor to start."""
    info = MagicMock()
    info.address = ADDRESS
    with (
        patch.object(integration, "async_address_present", return_value=True),
        patch.object(integration, "async_last_service_info", return_value=info),
        patch.object(integration, "async_process_advertisements") as wait,
        patch.object(
            integration,
            "async_validate_device",
            new_callable=AsyncMock,
            return_value=validation,
        ) as validate,
        patch.object(integration, "BMxBluetoothCoordinator") as coordinator,
        patch.object(
            hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)

    validate.assert_awaited_once_with(hass, info)
    wait.assert_not_called()
    assert entry.runtime_data is coordinator.return_value
    coordinator.return_value.async_start.assert_called_once()


async def test_setup_waits_for_advertisement(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """A fresh passive-only packet is sufficient when no packet is cached."""
    info = MagicMock()
    info.address = ADDRESS

    async def receive(
        _hass: HomeAssistant,
        predicate: Callable[[BluetoothServiceInfoBleak], bool],
        matcher: dict[str, object],
        mode: BluetoothScanningMode,
        timeout: float,
    ) -> BluetoothServiceInfoBleak:
        assert predicate(info)
        assert matcher == {"address": ADDRESS, "connectable": False}
        assert mode is BluetoothScanningMode.PASSIVE
        assert timeout == integration.SETUP_ADVERTISEMENT_TIMEOUT
        return info

    with (
        patch.object(integration, "async_address_present", return_value=False),
        patch.object(integration, "async_last_service_info") as cached,
        patch.object(integration, "async_process_advertisements", side_effect=receive),
        patch.object(
            integration,
            "async_validate_device",
            new_callable=AsyncMock,
            return_value="valid_passive",
        ) as validate,
        patch.object(integration, "BMxBluetoothCoordinator"),
        patch.object(
            hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
    cached.assert_not_called()
    validate.assert_awaited_once_with(hass, info)


async def test_setup_retries_when_device_is_absent(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """No advertisement is a temporary failure, not proof of a wrong device."""
    with (
        patch.object(integration, "async_address_present", return_value=False),
        patch.object(
            integration, "async_process_advertisements", side_effect=TimeoutError
        ),
        patch.object(
            integration, "async_validate_device", new_callable=AsyncMock
        ) as validate,
        patch.object(integration, "BMxBluetoothCoordinator") as coordinator,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    validate.assert_not_awaited()
    coordinator.assert_not_called()


@pytest.mark.parametrize(
    ("validation", "expected_state"),
    [
        ("cannot_validate", ConfigEntryState.SETUP_RETRY),
        ("not_bm2", ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_validation_failure(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    validation: str,
    expected_state: ConfigEntryState,
) -> None:
    """Distinguish temporary BLE trouble from a proven protocol rejection."""
    with (
        patch.object(integration, "async_address_present", return_value=True),
        patch.object(integration, "async_last_service_info", return_value=MagicMock()),
        patch.object(
            integration,
            "async_validate_device",
            new_callable=AsyncMock,
            return_value=validation,
        ),
        patch.object(integration, "BMxBluetoothCoordinator") as coordinator,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is expected_state
    coordinator.assert_not_called()


@pytest.mark.parametrize(
    "connectable",
    [pytest.param(True, id="advertiser"), pytest.param(False, id="other-path")],
)
async def test_poll_callback(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    connectable: bool,
) -> None:
    """Poll the advertising device or another connectable path to it."""
    info = MagicMock()
    info.address = ADDRESS
    info.device.address = ADDRESS
    info.connectable = connectable
    active_device = MagicMock()
    data = MagicMock()
    data.async_poll_sensors = AsyncMock()
    with (
        patch.object(integration, "async_address_present", return_value=True),
        patch.object(integration, "async_last_service_info", return_value=info),
        patch.object(
            integration, "async_validate_device", return_value="valid_passive"
        ),
        patch.object(integration, "BMxBluetoothDeviceData", return_value=data),
        patch.object(integration, "BMxBluetoothCoordinator") as coordinator,
        patch.object(hass.config_entries, "async_forward_entry_setups"),
        patch.object(
            integration, "async_ble_device_from_address", return_value=active_device
        ) as find_device,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        poll = coordinator.call_args.kwargs["poll_method"]
        assert await poll(info) is data.async_poll_sensors.return_value
    expected_device = info.device if connectable else active_device
    data.async_poll_sensors.assert_awaited_once_with(expected_device)
    assert find_device.call_count == int(not connectable)


async def test_poll_callback_without_connectable_path(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """A poll that finds no connectable path fails instead of using old data."""
    info = MagicMock()
    info.device.address = ADDRESS
    info.connectable = False
    data = MagicMock()
    data.async_poll_sensors = AsyncMock()
    with (
        patch.object(integration, "async_address_present", return_value=True),
        patch.object(integration, "async_last_service_info", return_value=info),
        patch.object(
            integration, "async_validate_device", return_value="valid_passive"
        ),
        patch.object(integration, "BMxBluetoothDeviceData", return_value=data),
        patch.object(integration, "BMxBluetoothCoordinator") as coordinator,
        patch.object(hass.config_entries, "async_forward_entry_setups"),
        patch.object(integration, "async_ble_device_from_address", return_value=None),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        poll = coordinator.call_args.kwargs["poll_method"]
        with pytest.raises(RuntimeError, match="No connectable path"):
            await poll(info)
    data.async_poll_sensors.assert_not_awaited()


@pytest.mark.parametrize(
    ("state", "needed", "has_path", "expected"),
    [
        pytest.param(CoreState.starting, True, True, False, id="starting"),
        pytest.param(CoreState.running, False, True, False, id="not-needed"),
        pytest.param(CoreState.running, True, False, False, id="no-connectable-path"),
        pytest.param(CoreState.running, True, True, True, id="due"),
    ],
)
async def test_poll_gate(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    state: CoreState,
    needed: bool,
    has_path: bool,
    expected: bool,
) -> None:
    """Poll only while HA runs, a read is due and a connectable path exists."""
    info = MagicMock()
    info.device.address = ADDRESS
    data = MagicMock()
    data.poll_needed.return_value = needed
    with (
        patch.object(integration, "async_address_present", return_value=True),
        patch.object(integration, "async_last_service_info", return_value=info),
        patch.object(
            integration, "async_validate_device", return_value="valid_passive"
        ),
        patch.object(integration, "BMxBluetoothDeviceData", return_value=data),
        patch.object(integration, "BMxBluetoothCoordinator") as coordinator,
        patch.object(hass.config_entries, "async_forward_entry_setups"),
        patch.object(hass, "state", state),
        patch.object(
            integration,
            "async_ble_device_from_address",
            return_value=MagicMock() if has_path else None,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        needs_poll = coordinator.call_args.kwargs["needs_poll_method"]
        assert needs_poll(info, 12.0) is expected
    assert data.poll_needed.call_count == int(state is CoreState.running)


ENHANCED_MANUFACTURER_ID = 27928
ENHANCED_BODY = bytes.fromhex("95185a633bc8fafdea8897c7c435")


async def test_setup_seeds_generation(hass: HomeAssistant) -> None:
    """The setup advertisement sets the generation before the first poll check."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ADDRESS,
        options={CONF_BATTERY_TYPE: Battery.leadacid.value},
    )
    entry.add_to_hass(hass)
    info = MagicMock()
    info.device.address = ADDRESS
    info.manufacturer_data = {ENHANCED_MANUFACTURER_ID: ENHANCED_BODY}
    info.raw = (
        bytes([len(ENHANCED_BODY) + 3, 0xFF])
        + ENHANCED_MANUFACTURER_ID.to_bytes(2, "little")
        + ENHANCED_BODY
    )
    with (
        patch.object(integration, "async_address_present", return_value=True),
        patch.object(integration, "async_last_service_info", return_value=info),
        patch.object(
            integration, "async_validate_device", return_value="valid_passive"
        ),
        patch.object(integration, "BMxBluetoothCoordinator") as coordinator,
        patch.object(hass.config_entries, "async_forward_entry_setups"),
        patch.object(
            integration, "async_ble_device_from_address", return_value=MagicMock()
        ),
        patch.object(hass, "state", CoreState.running),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        kwargs = coordinator.call_args.kwargs
        assert kwargs["update_method"].__self__.bm2_generation is (
            BM2Generation.ENHANCED
        )
        # Enhanced with a chosen chemistry never connects, even before any
        # advertisement reaches the coordinator.
        assert not kwargs["needs_poll_method"](info, None)


@pytest.mark.parametrize(
    ("unload_error", "success", "expected_state"),
    [
        pytest.param(None, True, ConfigEntryState.NOT_LOADED, id="success"),
        pytest.param(
            ConfigEntryError("Platform unload failed"),
            False,
            ConfigEntryState.FAILED_UNLOAD,
            id="failure",
        ),
    ],
)
async def test_unload(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    unload_error: ConfigEntryError | None,
    success: bool,
    expected_state: ConfigEntryState,
) -> None:
    """Exercise unload through the config-entry manager."""
    with (
        patch.object(integration, "async_address_present", return_value=True),
        patch.object(integration, "async_last_service_info", return_value=MagicMock()),
        patch.object(
            integration, "async_validate_device", return_value="valid_passive"
        ),
        patch.object(integration, "BMxBluetoothCoordinator"),
        patch.object(hass.config_entries, "async_forward_entry_setups"),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        with patch.object(
            hass.config_entries,
            "async_unload_platforms_or_raise",
            side_effect=unload_error,
            return_value=None,
        ) as unload:
            assert await hass.config_entries.async_unload(entry.entry_id) is success
    unload.assert_awaited_once_with(entry, integration.PLATFORMS)
    assert entry.state is expected_state
