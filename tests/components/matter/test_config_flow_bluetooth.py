"""Test the Matter config flow Bluetooth discovery."""

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
        "name": MATTER_BLE_NAME,
        "vendor_id": "0xFFF1",
        "product_id": "0x8000",
        "discriminator": "3840",
    }
    (flow,) = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert flow["context"]["unique_id"] == UNIQUE_ID
    assert flow["context"]["title_placeholders"] == {"name": MATTER_BLE_NAME}


@pytest.mark.usefixtures("bluetooth_enabled", "integration")
async def test_discovery_without_name(hass: HomeAssistant) -> None:
    """A nameless advertisement is titled by its discriminator."""
    result = await _async_start_discovery(hass, matter_ble_service_info(name=""))
    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"]["name"] == "Matter device 3840"


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
async def test_address_rotation_supersedes_flow(hass: HomeAssistant) -> None:
    """A new address for the same device replaces the older discovery."""
    await _async_start_discovery(hass)
    second = await _async_start_discovery(
        hass, matter_ble_service_info(address=ROTATED_ADDRESS)
    )
    assert second["type"] is FlowResultType.FORM
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["flow_id"] for flow in flows] == [second["flow_id"]]


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
