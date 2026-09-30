"""Tests for setting up a BM2 monitor from an existing config entry."""

from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components import bmx_monitor as integration
from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bmx_monitor.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import CoreState, HomeAssistant

from tests.common import MockConfigEntry

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
        patch.object(integration, "ActiveBluetoothProcessorCoordinator") as coordinator,
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
        patch.object(integration, "ActiveBluetoothProcessorCoordinator"),
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
        patch.object(integration, "ActiveBluetoothProcessorCoordinator") as coordinator,
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
        patch.object(integration, "ActiveBluetoothProcessorCoordinator") as coordinator,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is expected_state
    coordinator.assert_not_called()


@pytest.mark.parametrize("connectable", [True, False])
@pytest.mark.parametrize("has_active_path", [True, False])
async def test_poll_callback(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    connectable: bool,
    has_active_path: bool,
) -> None:
    """Poll the advertising device, another active path, or passive fallback."""
    info = MagicMock()
    info.address = ADDRESS
    info.device.address = ADDRESS
    info.connectable = connectable
    active_device = MagicMock() if has_active_path else None
    data = MagicMock()
    data.async_poll = AsyncMock()
    with (
        patch.object(integration, "async_address_present", return_value=True),
        patch.object(integration, "async_last_service_info", return_value=info),
        patch.object(
            integration, "async_validate_device", return_value="valid_passive"
        ),
        patch.object(integration, "BMxBluetoothDeviceData", return_value=data),
        patch.object(integration, "ActiveBluetoothProcessorCoordinator") as coordinator,
        patch.object(hass.config_entries, "async_forward_entry_setups"),
        patch.object(
            integration, "async_ble_device_from_address", return_value=active_device
        ) as find_device,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        poll = coordinator.call_args.kwargs["poll_method"]
        assert await poll(info) is data.async_poll.return_value
    expected_device = info.device if connectable else active_device
    data.async_poll.assert_awaited_once_with(expected_device)
    assert find_device.call_count == int(not connectable)


@pytest.mark.parametrize(
    ("state", "needed", "expected"),
    [
        (CoreState.starting, True, False),
        (CoreState.running, False, False),
        (CoreState.running, True, True),
    ],
)
async def test_poll_gate(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    state: CoreState,
    needed: bool,
    expected: bool,
) -> None:
    """Poll only while HA runs and the device's schedule permits it."""
    info = MagicMock()
    data = MagicMock()
    data.poll_needed.return_value = needed
    with (
        patch.object(integration, "async_address_present", return_value=True),
        patch.object(integration, "async_last_service_info", return_value=info),
        patch.object(
            integration, "async_validate_device", return_value="valid_passive"
        ),
        patch.object(integration, "BMxBluetoothDeviceData", return_value=data),
        patch.object(integration, "ActiveBluetoothProcessorCoordinator") as coordinator,
        patch.object(hass.config_entries, "async_forward_entry_setups"),
        patch.object(hass, "state", state),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        needs_poll = coordinator.call_args.kwargs["needs_poll_method"]
        assert needs_poll(info, 12.0) is expected
    assert data.poll_needed.call_count == int(state is CoreState.running)


@pytest.mark.parametrize("success", [True, False])
async def test_unload(
    hass: HomeAssistant, entry: MockConfigEntry, success: bool
) -> None:
    """Exercise unload through the config-entry manager."""
    with (
        patch.object(integration, "async_address_present", return_value=True),
        patch.object(integration, "async_last_service_info", return_value=MagicMock()),
        patch.object(
            integration, "async_validate_device", return_value="valid_passive"
        ),
        patch.object(integration, "ActiveBluetoothProcessorCoordinator"),
        patch.object(hass.config_entries, "async_forward_entry_setups"),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        with patch.object(
            hass.config_entries, "async_unload_platforms", return_value=success
        ) as unload:
            assert await hass.config_entries.async_unload(entry.entry_id) is success
    unload.assert_awaited_once_with(entry, integration.PLATFORMS)
