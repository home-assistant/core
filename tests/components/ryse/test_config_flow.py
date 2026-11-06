"""Tests for the RYSE BLE config flow."""

from __future__ import annotations

from collections.abc import Callable, Generator
from unittest.mock import AsyncMock, MagicMock, patch

from bleak.exc import BleakError
import pytest

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.ryse.const import DOMAIN, MANUFACTURER_ID
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    DEVICE_ADDRESS,
    DEVICE_NAME,
    LOCAL_SOURCE,
    LOCAL_SOURCE_HCI1,
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


async def test_async_step_user_pairs_on_strongest_local_adapter(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test user pairing uses the strongest local adapter, not registration order."""
    weak_device = make_ble_device()
    strong_device = make_ble_device()
    weak_adv = make_advertisement(rssi=-80)
    strong_adv = make_advertisement(rssi=-40)
    cancel_weak = register_local_scanner(hass, weak_device, weak_adv)
    cancel_strong = register_local_scanner(
        hass, strong_device, strong_adv, source=LOCAL_SOURCE_HCI1, adapter="hci1"
    )
    inject_ryse(hass, weak_device, weak_adv)
    await _abort_bluetooth_flows(hass)
    try:
        with patch(
            "homeassistant.components.ryse.config_flow.RyseBLEDevice",
            return_value=mock_device,
        ) as mock_cls:
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_USER}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], USER_INPUT
            )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        mock_cls.assert_called_once_with(strong_device)
        mock_device.pair.assert_awaited_once()
    finally:
        cancel_weak()
        cancel_strong()


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


async def test_async_step_user_uses_local_pair_when_proxy_is_idle(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test a local PAIR advertisement is used even if the manager selected idle proxy data."""
    device = make_ble_device()
    remote, cancel_remote = register_remote_scanner(hass)
    remote.inject_advertisement(device, make_advertisement(pairing=False))
    cancel_local = register_local_scanner(hass, device, make_advertisement())
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


async def test_async_step_user_skips_when_only_proxy_is_pairing(
    hass: HomeAssistant,
) -> None:
    """Test an idle local advertisement is not rescued by a proxy PAIR packet."""
    device = make_ble_device()
    remote, cancel_remote = register_remote_scanner(hass)
    remote.inject_advertisement(device, make_advertisement())
    cancel_local = register_local_scanner(
        hass, device, make_advertisement(pairing=False)
    )
    await _abort_bluetooth_flows(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
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
    assert len(flows) == 1
    assert flows[0]["step_id"] == "bluetooth_confirm"
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
    """Test an idle shade stays on one confirm form so it can be ignored."""
    device = make_ble_device()
    cancel = register_local_scanner(hass, device, make_advertisement(pairing=False))
    inject_ryse(hass, device, make_advertisement(pairing=False), LOCAL_SOURCE)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["step_id"] == "bluetooth_confirm"

    # A later advertisement with different payload must not start another flow.
    inject_ryse(
        hass,
        device,
        make_advertisement(manufacturer_data={MANUFACTURER_ID: b"\x8c\x11\x22\x33"}),
        LOCAL_SOURCE,
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 1

    result = await hass.config_entries.flow.async_configure(
        flows[0]["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "not_in_pairing_mode"}
    mock_device.pair.assert_not_called()
    cancel()


async def test_async_step_bluetooth_rejects_proxy_source(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test a proxy-only discovery stays confirmable and cannot pair."""
    device = make_ble_device()
    advertisement = make_advertisement()
    scanner, cancel = register_remote_scanner(hass)
    scanner.inject_advertisement(device, advertisement)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    result = await hass.config_entries.flow.async_configure(
        flows[0]["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "not_local_source"}
    mock_device.pair.assert_not_called()
    cancel()


async def test_async_step_bluetooth_proxy_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a proxy discovery of an existing entry aborts."""
    device = make_ble_device()
    advertisement = make_advertisement()
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


async def test_async_step_bluetooth_uses_local_pair_when_proxy_is_idle(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test bluetooth discovery uses the local PAIR packet when a proxy reports idle."""
    device = make_ble_device()
    remote, cancel_remote = register_remote_scanner(hass)
    cancel_local = register_local_scanner(hass, device, make_advertisement())
    try:
        remote.inject_advertisement(device, make_advertisement(pairing=False))
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


async def test_async_step_bluetooth_rejects_idle_local_when_proxy_is_pairing(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test bluetooth discovery is aborted when only the proxy still has the PAIR flag."""
    device = make_ble_device()
    remote, cancel_remote = register_remote_scanner(hass)
    cancel_local = register_local_scanner(
        hass, device, make_advertisement(pairing=False)
    )
    try:
        remote.inject_advertisement(device, make_advertisement())
        await hass.async_block_till_done(wait_background_tasks=True)

        flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        assert len(flows) == 1
        result = await hass.config_entries.flow.async_configure(
            flows[0]["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "not_in_pairing_mode"}
        mock_device.pair.assert_not_called()
    finally:
        cancel_local()
        cancel_remote()


async def test_async_step_bluetooth_uses_scanner_not_manager_history(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test submit follows the local scanner, not a newer manager advertisement."""
    device = make_ble_device()
    idle = make_advertisement(pairing=False)
    pairing = make_advertisement()
    cancel = register_local_scanner(hass, device, idle)
    inject_ryse(hass, device, idle, LOCAL_SOURCE)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    flow_id = flows[0]["flow_id"]

    inject_ryse(hass, device, pairing, LOCAL_SOURCE)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 1

    result = await hass.config_entries.flow.async_configure(flow_id, user_input={})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "not_in_pairing_mode"}
    mock_device.pair.assert_not_called()

    cancel()
    cancel = register_local_scanner(hass, device, pairing)
    result = await hass.config_entries.flow.async_configure(flow_id, user_input={})
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

    cancel()
    idle = make_advertisement(pairing=False)
    cancel = register_local_scanner(hass, device, idle)
    inject_ryse(hass, device, idle, LOCAL_SOURCE)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(flow_id, user_input={})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "not_in_pairing_mode"}
    mock_device.pair.assert_not_called()

    cancel()
    cancel = register_local_scanner(hass, device, pairing)
    inject_ryse(hass, device, pairing, LOCAL_SOURCE)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(flow_id, user_input={})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    mock_device.pair.assert_awaited_once()
    cancel()


async def test_async_step_bluetooth_idle_then_pair(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test an open idle discovery pairs once the PAIR flag appears."""
    device = make_ble_device()
    cancel = register_local_scanner(hass, device, make_advertisement(pairing=False))
    inject_ryse(hass, device, make_advertisement(pairing=False), LOCAL_SOURCE)
    await hass.async_block_till_done(wait_background_tasks=True)
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    flow_id = flows[0]["flow_id"]
    mock_device.pair.assert_not_called()

    inject_ryse(hass, device, make_advertisement(), LOCAL_SOURCE)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 1

    cancel()
    cancel = register_local_scanner(hass, device, make_advertisement())
    result = await hass.config_entries.flow.async_configure(flow_id, user_input={})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    mock_device.pair.assert_awaited_once()
    cancel()


async def test_async_step_bluetooth_proxy_then_local(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test an open proxy discovery pairs once a local adapter sees the shade."""
    device = make_ble_device()
    advertisement = make_advertisement()
    remote, cancel_remote = register_remote_scanner(hass)
    cancel_local: Callable[[], None] | None = None
    try:
        remote.inject_advertisement(device, advertisement)
        await hass.async_block_till_done(wait_background_tasks=True)

        flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        assert len(flows) == 1
        flow_id = flows[0]["flow_id"]
        result = await hass.config_entries.flow.async_configure(flow_id, user_input={})
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "not_local_source"}
        mock_device.pair.assert_not_called()

        remote.inject_advertisement(device, advertisement)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 1

        cancel_local = register_local_scanner(hass, device, advertisement)
        result = await hass.config_entries.flow.async_configure(flow_id, user_input={})
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


async def test_reauth_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test reauth re-pairs the shade and reloads the entry."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"] == {"name": mock_config_entry.title}

    cancel, _ = _see_on_local(hass)
    await _abort_bluetooth_flows(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    mock_device.pair.assert_awaited_once()
    cancel()


async def test_reauth_not_in_pairing_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test reauth stays on the form until the shade is in pairing mode."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    cancel, _ = _see_on_local(hass, pairing=False)
    await _abort_bluetooth_flows(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "not_in_pairing_mode"}
    mock_device.pair.assert_not_called()
    cancel()


async def test_reauth_not_local_source(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test reauth reports when the shade is not on a local adapter."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "not_local_source"}
    mock_device.pair.assert_not_called()
