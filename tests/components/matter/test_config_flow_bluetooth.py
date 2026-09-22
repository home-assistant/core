"""Test the Matter config flow Bluetooth discovery."""

import asyncio
from datetime import timedelta
from unittest.mock import MagicMock, call, patch

from freezegun.api import FrozenDateTimeFactory
from matter_server.common.errors import NodeCommissionFailed
import pytest

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.matter.const import DOMAIN
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_IGNORE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .common import (
    MATTER_BLE_ADDRESS,
    MATTER_BLE_NAME,
    MATTER_BLE_SERVICE_DATA,
    matter_ble_service_info,
)

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.bluetooth import (
    _get_manager,
    generate_advertisement_data,
    generate_ble_device,
    inject_advertisement_with_time_and_source_connectable,
)

RAW_COMMISSIONABLE = bytes([0x0B, 0x16, 0xF6, 0xFF, *MATTER_BLE_SERVICE_DATA])
RAW_OTHER = bytes([0x05, 0x16, 0xF0, 0xFF, 0x01, 0x02])
ROTATED_ADDRESS = "AA:BB:CC:DD:EE:F1"
UNIQUE_ID = "fff18000f00"
PAIRING_CODE = "MT:Y.K9042C00KA0648G00"


def _inject_raw(hass: HomeAssistant, raw: bytes, time: float) -> None:
    """Inject a packet for the discovered address with the given raw bytes."""
    inject_advertisement_with_time_and_source_connectable(
        hass,
        generate_ble_device(address=MATTER_BLE_ADDRESS, name=MATTER_BLE_NAME),
        generate_advertisement_data(local_name=MATTER_BLE_NAME),
        time,
        "local",
        True,
        raw=raw,
    )


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture(name="bluetooth_enabled")
def bluetooth_enabled_fixture(matter_client: MagicMock) -> None:
    """Report Bluetooth support from the Matter server."""
    matter_client.server_info.bluetooth_enabled = True


async def _async_start_discovery(
    hass: HomeAssistant, service_info: BluetoothServiceInfoBleak | None = None
) -> dict:
    """Start a Bluetooth discovery flow."""
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=service_info or matter_ble_service_info(),
    )


async def test_no_entry_routes_to_setup(hass: HomeAssistant) -> None:
    """Without a Matter entry the discovery offers to set up the integration."""
    result = await _async_start_discovery(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"


@pytest.mark.usefixtures("bluetooth_enabled", "integration")
async def test_discovery_shows_confirm(hass: HomeAssistant) -> None:
    """A loaded server with Bluetooth shows the commissioning form."""
    result = await _async_start_discovery(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["description_placeholders"] == {
        "name": f"{MATTER_BLE_NAME}-DDEEF0",
        "vendor_id": "0xFFF1",
        "product_id": "0x8000",
        "discriminator": "3840",
    }
    (flow,) = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert flow["context"]["unique_id"] == UNIQUE_ID
    assert flow["context"]["title_placeholders"] == {
        "name": f"{MATTER_BLE_NAME}-DDEEF0"
    }


@pytest.mark.parametrize(
    ("name", "title"),
    [
        pytest.param("", "Matter-DDEEF0", id="nameless"),
        pytest.param(
            "Shelly1MiniG4-A085E3B31284", "Shelly1MiniG4-A085E3B31284", id="mac_in_name"
        ),
    ],
)
@pytest.mark.usefixtures("bluetooth_enabled", "integration")
async def test_discovery_title(hass: HomeAssistant, name: str, title: str) -> None:
    """Names without a MAC get the short MAC appended, like Shelly names have."""
    result = await _async_start_discovery(hass, matter_ble_service_info(name=name))
    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"]["name"] == title


async def test_only_ignored_entries_is_not_a_server(hass: HomeAssistant) -> None:
    """An ignored device on its own does not count as a Matter server."""
    MockConfigEntry(
        domain=DOMAIN, source=SOURCE_IGNORE, unique_id=UNIQUE_ID
    ).add_to_hass(hass)
    result = await _async_start_discovery(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_entry_not_loaded_shows_confirm(hass: HomeAssistant) -> None:
    """A device is still discovered while the server is unavailable."""
    MockConfigEntry(domain=DOMAIN, data={"url": "ws://localhost:5580/ws"}).add_to_hass(
        hass
    )
    result = await _async_start_discovery(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"


@pytest.mark.usefixtures("integration")
async def test_server_without_bluetooth(hass: HomeAssistant) -> None:
    """A server without Bluetooth cannot commission discovered devices."""
    result = await _async_start_discovery(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "bluetooth_not_supported"


@pytest.mark.parametrize(
    "service_data",
    [
        pytest.param(
            bytes([0x01, *MATTER_BLE_SERVICE_DATA[1:]]), id="not_commissionable"
        ),
        pytest.param(MATTER_BLE_SERVICE_DATA[:7], id="short"),
    ],
)
@pytest.mark.usefixtures("bluetooth_enabled", "integration")
async def test_invalid_advertisement(hass: HomeAssistant, service_data: bytes) -> None:
    """Advertisements that are not commissionable are ignored."""
    result = await _async_start_discovery(
        hass, matter_ble_service_info(service_data=service_data)
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_commissionable"


@pytest.mark.usefixtures("bluetooth_enabled", "integration")
async def test_ignored_device(hass: HomeAssistant) -> None:
    """An ignored device stays ignored after its address rotates."""
    MockConfigEntry(
        domain=DOMAIN, source=SOURCE_IGNORE, unique_id=UNIQUE_ID
    ).add_to_hass(hass)
    result = await _async_start_discovery(
        hass, matter_ble_service_info(address=ROTATED_ADDRESS)
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("bluetooth_enabled", "integration")
async def test_colliding_devices_keep_separate_cards(hass: HomeAssistant) -> None:
    """Identical products with the same discriminator are told apart by address."""
    first = await _async_start_discovery(hass)
    second = await _async_start_discovery(
        hass, matter_ble_service_info(address=ROTATED_ADDRESS)
    )
    assert second["type"] is FlowResultType.FORM
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert {flow["flow_id"] for flow in flows} == {first["flow_id"], second["flow_id"]}
    assert {flow["context"]["title_placeholders"]["name"] for flow in flows} == {
        f"{MATTER_BLE_NAME}-DDEEF0",
        f"{MATTER_BLE_NAME}-DDEEF1",
    }

    # Ignoring one card ignores the product identity, whatever the address.
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IGNORE},
        data={"unique_id": UNIQUE_ID, "title": MATTER_BLE_NAME},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    result = await _async_start_discovery(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("bluetooth_enabled", "integration")
async def test_same_address_discovery_aborts(hass: HomeAssistant) -> None:
    """Rediscovery of the same address keeps the existing card."""
    first = await _async_start_discovery(hass)
    second = await _async_start_discovery(hass)
    assert second["type"] is FlowResultType.ABORT
    assert second["reason"] == "already_in_progress"
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["flow_id"] for flow in flows] == [first["flow_id"]]


@pytest.mark.usefixtures("bluetooth_enabled", "integration")
async def test_stale_discovery_is_dropped(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The discovery goes away when the device stops advertising as commissionable."""
    now = 1000.0

    def _advance(seconds: float) -> None:
        nonlocal now
        now += seconds
        freezer.tick(timedelta(seconds=seconds))
        async_fire_time_changed(hass)

    # Keep the bluetooth manager's clock in step so it does not expire the device.
    with (
        patch(
            "homeassistant.components.bluetooth.MONOTONIC_TIME",
            side_effect=lambda: now,
        ),
        patch(
            "habluetooth.manager.monotonic_time_coarse",
            side_effect=lambda: now,
        ),
        patch(
            "homeassistant.components.bluetooth.async_clear_address_from_match_history"
        ) as clear_history,
    ):
        result = await _async_start_discovery(hass)
        assert result["type"] is FlowResultType.FORM

        _advance(40)
        _inject_raw(hass, RAW_COMMISSIONABLE, now)
        await hass.async_block_till_done()

        _advance(40)
        await hass.async_block_till_done()
        assert hass.config_entries.flow.async_progress_by_handler(DOMAIN)

        # A packet without Matter service data does not keep the discovery alive.
        _inject_raw(hass, RAW_OTHER, now)
        _advance(10)
        await hass.async_block_till_done()
        assert hass.config_entries.flow.async_progress_by_handler(DOMAIN)

        _advance(20)
        await hass.async_block_till_done()
        assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert clear_history.call_args == call(hass, MATTER_BLE_ADDRESS)


@pytest.mark.usefixtures("bluetooth_enabled", "integration")
async def test_commission_success(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """Submitting a pairing code commissions the device over Bluetooth."""
    result = await _async_start_discovery(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"code": f" {PAIRING_CODE} "}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "commission_successful"
    matter_client.commission_with_code.assert_awaited_once_with(
        PAIRING_CODE, network_only=False
    )


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(
            NodeCommissionFailed("test_id", "1", "Failed"),
            "commission_failed",
            id="matter_error",
        ),
        pytest.param(RuntimeError("boom"), "unknown", id="unexpected"),
    ],
)
@pytest.mark.usefixtures("bluetooth_enabled", "integration")
async def test_commission_errors(
    hass: HomeAssistant,
    matter_client: MagicMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Commissioning failures are shown on the form."""
    matter_client.commission_with_code.side_effect = side_effect
    result = await _async_start_discovery(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"code": PAIRING_CODE}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] == {"base": error}


@pytest.mark.usefixtures("bluetooth_enabled")
async def test_commission_without_loaded_entry(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """Submitting while the server is unavailable aborts."""
    result = await _async_start_discovery(hass)
    await hass.config_entries.async_unload(integration.entry_id)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"code": PAIRING_CODE}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_loaded"


@pytest.mark.usefixtures("bluetooth_enabled", "integration")
async def test_commissioning_in_progress_is_never_aborted(
    hass: HomeAssistant, matter_client: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """A flow that started commissioning survives the device going silent."""
    commissioning = asyncio.Event()

    async def _commission(*_args: object, **_kwargs: object) -> None:
        await commissioning.wait()

    matter_client.commission_with_code.side_effect = _commission
    result = await _async_start_discovery(hass)
    configure = hass.async_create_background_task(
        hass.config_entries.flow.async_configure(
            result["flow_id"], {"code": PAIRING_CODE}
        ),
        "commission",
    )
    await asyncio.sleep(0)

    # The device stops advertising while the server is connected to it.
    freezer.tick(timedelta(seconds=120))
    async_fire_time_changed(hass)
    _get_manager()._address_disappeared(MATTER_BLE_ADDRESS)
    await hass.async_block_till_done()
    # A rotated address gets its own card and does not touch this one.
    rotated = await _async_start_discovery(
        hass, matter_ble_service_info(address=ROTATED_ADDRESS)
    )
    assert rotated["type"] is FlowResultType.FORM
    assert {
        flow["flow_id"]
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    } == {result["flow_id"], rotated["flow_id"]}

    commissioning.set()
    result = await configure
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "commission_successful"
