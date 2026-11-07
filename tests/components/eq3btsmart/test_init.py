"""Test the eq3btsmart integration init."""

import asyncio
from collections.abc import Generator
from functools import partial
from unittest.mock import MagicMock, PropertyMock, patch

from eq3btsmart.exceptions import Eq3StateException, Eq3TimeoutException
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.bluetooth import generate_ble_device

from homeassistant.components.eq3btsmart.const import DOMAIN
from homeassistant.components.eq3btsmart.models import Eq3Config
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_MAC, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac

from .const import MAC

ENTITY_ID = "climate.aa_bb_cc_dd_ee_ff"


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a config entry added to hass."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_MAC: MAC},
        unique_id=format_mac(MAC),
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_ble_device() -> Generator[None]:
    """Make the thermostat discoverable."""
    with (
        patch("homeassistant.components.eq3btsmart.PLATFORMS", [Platform.CLIMATE]),
        patch(
            "homeassistant.components.eq3btsmart.bluetooth.async_ble_device_from_address",
            return_value=generate_ble_device(address=MAC, name="CC-RT-BLE"),
        ),
    ):
        yield


async def test_setup_retries_when_device_not_found(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup is retried with a diagnostic reason when the device is missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_MAC: MAC},
        unique_id=format_mac(MAC),
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.eq3btsmart.bluetooth."
        "async_address_reachability_diagnostics",
        return_value="mock reachability reason",
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert (
        f"[{format_mac(MAC)}] Device could not be found: mock reachability reason"
        in caplog.text
    )


@pytest.mark.usefixtures("mock_ble_device")
async def test_reconnect_after_partial_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_thermostat: MagicMock,
) -> None:
    """Test a connect that fails after the link is up is torn down and retried."""
    link_up = False
    connected = asyncio.Event()

    async def connect() -> None:
        nonlocal link_up
        if link_up:
            raise Eq3StateException("Already connected")
        link_up = True
        if mock_thermostat.async_connect.await_count == 1:
            raise Eq3TimeoutException("Timeout during status command")
        connected.set()

    async def disconnect() -> None:
        nonlocal link_up
        link_up = False

    type(mock_thermostat).is_connected = PropertyMock(side_effect=lambda: link_up)
    mock_thermostat.async_connect.side_effect = connect
    mock_thermostat.async_disconnect.side_effect = disconnect
    mock_thermostat.async_get_status.side_effect = asyncio.Event().wait

    with patch(
        "homeassistant.components.eq3btsmart.Eq3Config",
        partial(Eq3Config, scan_interval=0),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        async with asyncio.timeout(1):
            await connected.wait()
        await hass.async_block_till_done()

    assert mock_thermostat.async_connect.await_count == 2
    mock_thermostat.async_disconnect.assert_awaited_once()
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_ble_device")
async def test_unload_when_disconnected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_thermostat: MagicMock,
) -> None:
    """Test unloading succeeds and stops the worker when already disconnected."""
    polling = asyncio.Event()
    worker_cancelled = asyncio.Event()

    async def get_status() -> None:
        polling.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            worker_cancelled.set()
            raise

    mock_thermostat.async_get_status.side_effect = get_status
    mock_thermostat.async_disconnect.side_effect = Eq3StateException("Not connected")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    async with asyncio.timeout(1):
        await polling.wait()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert worker_cancelled.is_set()
