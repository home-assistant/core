"""Tests for the RYSE BLE config flow."""

from __future__ import annotations

from collections.abc import Callable, Generator
from unittest.mock import AsyncMock, MagicMock, patch

from bleak.exc import BleakError
import pytest

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.ryse.const import DATA_LOCAL_WAITERS, DOMAIN, SERVICE_UUID
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_IGNORE, SOURCE_USER
from homeassistant.const import CONF_ADDRESS, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    DEVICE_ADDRESS,
    DEVICE_NAME,
    LOCAL_SOURCE,
    PROXY_SOURCE,
    USER_INPUT,
    inject_ryse,
    make_advertisement,
    make_ble_device,
    register_local_scanner,
    register_remote_scanner,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

PAIRING_ERRORS = [
    (Exception("boom"), "unexpected_error"),
    (TimeoutError("timeout"), "cannot_connect"),
    (OSError("os error"), "cannot_connect"),
    (EOFError("eof"), "cannot_connect"),
    (BleakError("bleak error"), "cannot_connect"),
    (False, "cannot_connect"),
]


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent config-flow tests from loading the cover platform."""
    with patch(
        "homeassistant.components.ryse.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock


def _see_on_local(
    hass: HomeAssistant,
    *,
    pairing: bool = True,
    name: str | None = DEVICE_NAME,
    manufacturer_data: dict[int, bytes] | None = None,
    service_uuids: list[str] | None = None,
) -> tuple[Callable[[], None], object]:
    """Register a local scanner and inject an advertisement from that adapter."""
    device = make_ble_device(name)
    advertisement = make_advertisement(
        pairing=pairing,
        name=name,
        manufacturer_data=manufacturer_data,
        service_uuids=service_uuids,
    )
    cancel = register_local_scanner(hass, device, advertisement)
    inject_ryse(hass, device, advertisement, LOCAL_SOURCE)
    return cancel, device


async def _abort_bluetooth_flows(hass: HomeAssistant) -> None:
    """Abort discovery flows started by advertisement injection."""
    await hass.async_block_till_done(wait_background_tasks=True)
    for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN):
        if flow["context"].get("source") == SOURCE_BLUETOOTH:
            hass.config_entries.flow.async_abort(flow["flow_id"])
    await hass.async_block_till_done()


async def test_async_step_user_success(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test user flow succeeds and creates entry."""
    cancel, _ = _see_on_local(hass)
    await _abort_bluetooth_flows(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["data_schema"].schema[CONF_ADDRESS].container == {
        DEVICE_ADDRESS: f"{DEVICE_NAME} ({DEVICE_ADDRESS})",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEVICE_NAME
    assert result["data"] == {}
    assert result["result"].unique_id == DEVICE_ADDRESS
    mock_device.pair.assert_awaited_once()
    mock_device.unpair.assert_awaited_once()
    cancel()


@pytest.mark.parametrize(
    "unpair_error",
    [
        pytest.param(BleakError("unpair error"), id="bleak"),
        pytest.param(RuntimeError("unpair error"), id="unexpected"),
    ],
)
async def test_async_step_user_success_when_unpair_fails(
    hass: HomeAssistant, mock_device: MagicMock, unpair_error: Exception
) -> None:
    """Test a failed unpair after successful pairing still creates the entry."""
    mock_device.unpair.side_effect = unpair_error
    cancel, _ = _see_on_local(hass)
    await _abort_bluetooth_flows(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DEVICE_ADDRESS
    mock_device.pair.assert_awaited_once()
    mock_device.unpair.assert_awaited_once()
    cancel()


@pytest.mark.parametrize(
    "unpair_error",
    [
        pytest.param(BleakError("unpair error"), id="bleak"),
        pytest.param(RuntimeError("unpair error"), id="unexpected"),
    ],
)
async def test_async_step_user_cannot_connect_when_unpair_fails(
    hass: HomeAssistant, mock_device: MagicMock, unpair_error: Exception
) -> None:
    """Test a failed unpair after a pairing error still reports cannot_connect."""
    mock_device.pair.side_effect = BleakError("bleak error")
    mock_device.unpair.side_effect = unpair_error
    cancel, _ = _see_on_local(hass)
    await _abort_bluetooth_flows(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    mock_device.unpair.assert_awaited_once()
    cancel()


@pytest.mark.parametrize(("pair_result", "expected_error"), PAIRING_ERRORS)
async def test_async_step_user_errors(
    hass: HomeAssistant,
    mock_device: MagicMock,
    pair_result: Exception | bool,
    expected_error: str,
) -> None:
    """Test errors during user pairing can be recovered from."""
    mock_device.pair.side_effect = [pair_result, True]
    cancel, _ = _see_on_local(hass)
    await _abort_bluetooth_flows(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DEVICE_ADDRESS
    cancel()


async def test_async_step_user_keeps_device_after_pairing_error(
    hass: HomeAssistant,
    mock_device: MagicMock,
) -> None:
    """Test a pairing error keeps the selected device even if it leaves pairing mode."""
    mock_device.pair.side_effect = [False, True]
    cancel, _ = _see_on_local(hass)
    await _abort_bluetooth_flows(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    cancel()


async def test_async_step_user_device_added_between_steps(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that we abort if the device gets added in another flow."""
    cancel, _ = _see_on_local(hass)
    await _abort_bluetooth_flows(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    cancel()


async def test_async_step_user_no_devices_found(hass: HomeAssistant) -> None:
    """Test that we abort when no devices are discovered."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_async_step_user_skips_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that we skip already configured devices in user flow discovery."""
    mock_config_entry.add_to_hass(hass)
    cancel, _ = _see_on_local(hass)
    await _abort_bluetooth_flows(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
    cancel()


async def test_async_step_user_skips_nameless_device(hass: HomeAssistant) -> None:
    """Test that we skip nameless devices in user flow discovery."""
    device = make_ble_device()
    advertisement = make_advertisement()
    nameless = BluetoothServiceInfoBleak(
        name=None,
        address=DEVICE_ADDRESS,
        rssi=-40,
        manufacturer_data=advertisement.manufacturer_data,
        service_data={},
        service_uuids=advertisement.service_uuids,
        source=LOCAL_SOURCE,
        device=device,
        advertisement=advertisement,
        time=0,
        connectable=True,
        tx_power=-127,
    )
    with patch(
        "homeassistant.components.ryse.config_flow.async_discovered_service_info",
        return_value=[nameless],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_async_step_user_skips_non_pairing_device(hass: HomeAssistant) -> None:
    """Test that we skip devices that are not advertising pairing mode."""
    cancel, _ = _see_on_local(hass, pairing=False)
    await _abort_bluetooth_flows(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
    cancel()


async def test_async_step_user_skips_unmatched_device(hass: HomeAssistant) -> None:
    """Test that we skip devices that are not RYSE advertisements."""
    device = generate_ble_device(DEVICE_ADDRESS, "Generic Device")
    advertisement = generate_advertisement_data(
        local_name="Generic Device",
        manufacturer_data={999: b"\x01"},
        service_uuids=["00001234-0000-1000-8000-00805f9b34fb"],
        rssi=-40,
    )
    cancel = register_local_scanner(hass, device, advertisement)
    inject_ryse(hass, device, advertisement, LOCAL_SOURCE)
    await _abort_bluetooth_flows(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
    cancel()


async def test_async_step_user_skips_proxy_source(hass: HomeAssistant) -> None:
    """Test that we skip devices seen only through a Bluetooth proxy."""
    device = make_ble_device()
    advertisement = make_advertisement()
    scanner, cancel = register_remote_scanner(hass)
    scanner.inject_advertisement(device, advertisement)
    await _abort_bluetooth_flows(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
    cancel()


async def test_async_step_user_keeps_proxy_selected_when_also_local(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test a proxy-selected advertisement is kept if a local adapter also sees it."""
    device = make_ble_device()
    advertisement = make_advertisement()
    remote, cancel_remote = register_remote_scanner(hass)
    remote.inject_advertisement(device, advertisement)
    cancel_local = register_local_scanner(hass, device, advertisement)
    await _abort_bluetooth_flows(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    mock_device.pair.assert_awaited_once()
    cancel_local()
    cancel_remote()


async def test_bluetooth_discovery_from_manufacturer_id(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test a pairing advertisement matching manufacturer_id starts discovery."""
    cancel, _ = _see_on_local(hass, service_uuids=[])
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_configure(
        flows[0]["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DEVICE_ADDRESS
    mock_device.pair.assert_awaited_once()
    cancel()


async def test_bluetooth_discovery_from_service_uuid(hass: HomeAssistant) -> None:
    """Test a service-UUID advertisement still matches the bluetooth matcher."""
    cancel, _ = _see_on_local(hass, pairing=False, manufacturer_data={})
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert not flows
    cancel()


async def test_async_step_bluetooth(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test Bluetooth discovery flow."""
    cancel, _ = _see_on_local(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    result = await hass.config_entries.flow.async_configure(
        flows[0]["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEVICE_NAME
    assert result["data"] == {}
    assert result["result"].unique_id == DEVICE_ADDRESS
    mock_device.pair.assert_awaited_once()
    mock_device.unpair.assert_awaited_once()
    cancel()


@pytest.mark.parametrize(("pair_result", "error_text"), PAIRING_ERRORS)
async def test_async_step_bluetooth_errors(
    hass: HomeAssistant,
    mock_device: MagicMock,
    pair_result: Exception | bool,
    error_text: str,
) -> None:
    """Test Bluetooth discovery confirm errors can be recovered from."""
    mock_device.pair.side_effect = [pair_result, True]
    cancel, _ = _see_on_local(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    result = await hass.config_entries.flow.async_configure(
        flows[0]["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_text}

    result = await hass.config_entries.flow.async_configure(
        flows[0]["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    cancel()


async def test_async_step_bluetooth_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test abort if device already configured before bluetooth discovery."""
    mock_config_entry.add_to_hass(hass)
    cancel, _ = _see_on_local(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    cancel()


async def test_async_step_bluetooth_not_in_pairing_mode(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test idle advertisements are not shown as discoveries."""
    cancel, _ = _see_on_local(hass, pairing=False)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    mock_device.pair.assert_not_called()
    cancel()


async def test_async_step_bluetooth_rejects_proxy_source(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test proxy-only discoveries are aborted before the confirmation form."""
    device = make_ble_device()
    advertisement = make_advertisement()
    scanner, cancel = register_remote_scanner(hass)
    scanner.inject_advertisement(device, advertisement)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    mock_device.pair.assert_not_called()
    assert DEVICE_ADDRESS in hass.data[DATA_LOCAL_WAITERS]
    cancel()


async def test_proxy_local_waiter_unsubscribes_on_hass_stop(
    hass: HomeAssistant,
) -> None:
    """Test leftover proxy waiters are released when Home Assistant stops."""
    device = make_ble_device()
    advertisement = make_advertisement()
    scanner, cancel = register_remote_scanner(hass)
    scanner.inject_advertisement(device, advertisement)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert DEVICE_ADDRESS in hass.data[DATA_LOCAL_WAITERS]

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    assert DEVICE_ADDRESS not in hass.data[DATA_LOCAL_WAITERS]
    cancel()


async def test_user_setup_cancels_proxy_waiter(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test creating an entry another way drops a leftover proxy waiter."""
    device = make_ble_device()
    advertisement = make_advertisement()
    remote, cancel_remote = register_remote_scanner(hass)
    cancel_local: Callable[[], None] | None = None
    try:
        remote.inject_advertisement(device, advertisement)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert DEVICE_ADDRESS in hass.data[DATA_LOCAL_WAITERS]

        cancel_local = register_local_scanner(hass, device, advertisement)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert DEVICE_ADDRESS not in hass.data[DATA_LOCAL_WAITERS]
    finally:
        if cancel_local is not None:
            cancel_local()
        cancel_remote()


async def test_ignore_cancels_proxy_waiter(hass: HomeAssistant) -> None:
    """Test ignoring a shade drops a leftover proxy waiter."""
    device = make_ble_device()
    advertisement = make_advertisement()
    scanner, cancel = register_remote_scanner(hass)
    try:
        scanner.inject_advertisement(device, advertisement)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert DEVICE_ADDRESS in hass.data[DATA_LOCAL_WAITERS]

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IGNORE},
            data={"unique_id": DEVICE_ADDRESS, "title": DEVICE_NAME},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert DEVICE_ADDRESS not in hass.data[DATA_LOCAL_WAITERS]
    finally:
        cancel()


async def test_already_configured_cancels_proxy_waiter(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a later discovery of an existing entry drops a leftover proxy waiter."""
    device = make_ble_device()
    advertisement = make_advertisement()
    scanner, cancel = register_remote_scanner(hass)
    try:
        scanner.inject_advertisement(device, advertisement)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert DEVICE_ADDRESS in hass.data[DATA_LOCAL_WAITERS]

        mock_config_entry.add_to_hass(hass)
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_BLUETOOTH},
            data=BluetoothServiceInfoBleak(
                name=DEVICE_NAME,
                address=DEVICE_ADDRESS,
                rssi=-40,
                manufacturer_data=advertisement.manufacturer_data,
                service_data={},
                service_uuids=advertisement.service_uuids,
                source=PROXY_SOURCE,
                device=device,
                advertisement=advertisement,
                time=0,
                connectable=True,
                tx_power=-127,
            ),
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"
        assert DEVICE_ADDRESS not in hass.data[DATA_LOCAL_WAITERS]
    finally:
        cancel()


async def test_async_step_bluetooth_proxy_selected_when_also_local(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test bluetooth discovery proceeds when a proxy wins but a local adapter sees it."""
    device = make_ble_device()
    advertisement = make_advertisement()
    remote, cancel_remote = register_remote_scanner(hass)
    cancel_local = register_local_scanner(hass, device, advertisement)
    try:
        # Register the local adapter before the proxy advertisement so the
        # discovery flow can see a local route when it starts.
        remote.inject_advertisement(device, advertisement)
        await hass.async_block_till_done(wait_background_tasks=True)

        flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        assert len(flows) == 1
        result = await hass.config_entries.flow.async_configure(
            flows[0]["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        mock_device.pair.assert_awaited_once()
    finally:
        cancel_local()
        cancel_remote()


async def test_async_step_bluetooth_pairing_overrides_stale_idle(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test a PAIR advertisement is shown even if the scanner cache is still idle."""
    device = make_ble_device()
    idle = make_advertisement(pairing=False)
    pairing = make_advertisement()
    cancel = register_local_scanner(hass, device, idle)
    inject_ryse(hass, device, idle, LOCAL_SOURCE)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _abort_bluetooth_flows(hass)

    inject_ryse(hass, device, pairing, LOCAL_SOURCE)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    result = await hass.config_entries.flow.async_configure(
        flows[0]["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    mock_device.pair.assert_awaited_once()
    cancel()


async def test_async_step_bluetooth_lost_local_source(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test pairing is refused if the local adapter is gone, then can recover."""
    device = make_ble_device()
    advertisement = make_advertisement()
    cancel = register_local_scanner(hass, device, advertisement)
    inject_ryse(hass, device, advertisement, LOCAL_SOURCE)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    flow_id = flows[0]["flow_id"]
    cancel()

    result = await hass.config_entries.flow.async_configure(flow_id, user_input={})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "not_local_source"}
    mock_device.pair.assert_not_called()

    cancel = register_local_scanner(hass, device, advertisement)
    result = await hass.config_entries.flow.async_configure(flow_id, user_input={})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    mock_device.pair.assert_awaited_once()
    cancel()


async def test_async_step_bluetooth_left_pairing_mode(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test we refuse to pair if the shade leaves pairing mode before confirm."""
    device = make_ble_device()
    pairing = make_advertisement()
    cancel = register_local_scanner(hass, device, pairing)
    inject_ryse(hass, device, pairing, LOCAL_SOURCE)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    flow_id = flows[0]["flow_id"]

    inject_ryse(hass, device, make_advertisement(pairing=False), LOCAL_SOURCE)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(flow_id, user_input={})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "not_in_pairing_mode"}
    mock_device.pair.assert_not_called()

    inject_ryse(hass, device, pairing, LOCAL_SOURCE)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(flow_id, user_input={})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    mock_device.pair.assert_awaited_once()
    cancel()


async def test_async_step_bluetooth_idle_then_pair(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test an idle advertisement can be rediscovered after the PAIR flag appears."""
    device = make_ble_device()
    cancel = register_local_scanner(hass, device, make_advertisement(pairing=False))
    inject_ryse(hass, device, make_advertisement(pairing=False), LOCAL_SOURCE)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    mock_device.pair.assert_not_called()

    inject_ryse(hass, device, make_advertisement(), LOCAL_SOURCE)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    result = await hass.config_entries.flow.async_configure(
        flows[0]["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    mock_device.pair.assert_awaited_once()
    cancel()


async def test_async_step_bluetooth_proxy_then_local(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test a proxy-only abort rediscovers once a local adapter sees the shade."""
    device = make_ble_device()
    advertisement = make_advertisement()
    remote, cancel_remote = register_remote_scanner(hass)
    cancel_local: Callable[[], None] | None = None
    try:
        remote.inject_advertisement(device, advertisement)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        mock_device.pair.assert_not_called()
        assert DEVICE_ADDRESS in hass.data[DATA_LOCAL_WAITERS]

        remote.inject_advertisement(device, advertisement)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)

        cancel_local = register_local_scanner(hass, device, advertisement)
        # Identical ads are dropped by the Bluetooth manager; a payload change
        # is required to notify BluetoothCallbackMatcher subscribers.
        later = make_advertisement(service_data={SERVICE_UUID: b"\x01"})
        remote.inject_advertisement(device, later)
        await hass.async_block_till_done(wait_background_tasks=True)

        flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        assert len(flows) == 1
        assert DEVICE_ADDRESS not in hass.data.get(DATA_LOCAL_WAITERS, {})
        result = await hass.config_entries.flow.async_configure(
            flows[0]["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        mock_device.pair.assert_awaited_once()
    finally:
        if cancel_local is not None:
            cancel_local()
        cancel_remote()


async def test_async_step_bluetooth_fallback_name(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test Bluetooth discovery flow fallback name when service info name is empty."""
    device = make_ble_device("")
    advertisement = make_advertisement(name="")
    cancel = register_local_scanner(hass, device, advertisement)
    nameless = BluetoothServiceInfoBleak(
        name="",
        address=DEVICE_ADDRESS,
        rssi=-40,
        manufacturer_data=advertisement.manufacturer_data,
        service_data={},
        service_uuids=advertisement.service_uuids,
        source=LOCAL_SOURCE,
        device=device,
        advertisement=advertisement,
        time=0,
        connectable=True,
        tx_power=-127,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=nameless,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"] == {"name": "RYSE device"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "RYSE device"
    mock_device.pair.assert_awaited_once()
    cancel()
