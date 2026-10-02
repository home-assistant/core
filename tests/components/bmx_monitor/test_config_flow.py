"""Tests for the BM2 battery monitor config and options flows."""

from collections.abc import Callable, Iterator
from time import monotonic
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from bleak.exc import BleakError
from bmx_ble import BM2Generation
import probatio
import pytest

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bmx_monitor import (
    config_flow,
    validation as protocol_validation,
)
from homeassistant.components.bmx_monitor.const import (
    BM_NAMES,
    CONF_BATTERY_TYPE,
    CONF_CUSTOM_BATTERY_CHEMISTRY,
    CONF_CUSTOM_CHARGING_VOLTAGE,
    CONF_CUSTOM_CRITICAL_VOLTAGE,
    CONF_CUSTOM_FIFTY_PERCENT_VOLTAGE,
    CONF_CUSTOM_FLOATING_VOLTAGE,
    CONF_CUSTOM_HUNDRED_PERCENT_VOLTAGE,
    CONF_CUSTOM_LOW_VOLTAGE,
    CONF_CUSTOM_NUMPY_PERCENT,
    CONF_CUSTOM_NUMPY_VOLTS,
    CONF_RATE_LIMIT,
    CONF_RATE_LIMIT_MODE,
    DEFAULT_BATTERY_TYPE,
    DEFAULT_RATE_LIMIT,
    DEFAULT_RATE_LIMIT_MODE,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry
from tests.components.bluetooth import (
    async_setup_with_default_adapter,
    generate_advertisement_data,
    generate_ble_device,
    inject_advertisement_with_time_and_source_connectable,
)

ADDRESS = "AA:BB:CC:DD:EE:FF"
CUSTOM_DETAILS = {
    CONF_CUSTOM_BATTERY_CHEMISTRY: "Lead Acid",
    CONF_CUSTOM_CRITICAL_VOLTAGE: 11.0,
    CONF_CUSTOM_LOW_VOLTAGE: 11.5,
    CONF_CUSTOM_FIFTY_PERCENT_VOLTAGE: 12.3,
    CONF_CUSTOM_HUNDRED_PERCENT_VOLTAGE: 12.8,
    CONF_CUSTOM_FLOATING_VOLTAGE: 13.5,
    CONF_CUSTOM_CHARGING_VOLTAGE: 14.4,
}


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Iterator[None]:
    """Prevent a newly created entry from opening a real Bluetooth connection."""
    with patch(
        "homeassistant.components.bmx_monitor.async_setup_entry",
        return_value=True,
    ):
        yield


@pytest.fixture
def service_info() -> MagicMock:
    """Provide a discovered Bluetooth device without a physical adapter."""
    info = MagicMock(spec=BluetoothServiceInfoBleak)
    info.address = ADDRESS
    info.name = "BM2"
    return info


async def _manual_form(hass: HomeAssistant, service_info: MagicMock) -> dict:
    """Start manual selection with exactly one cached device."""
    with patch.object(
        config_flow,
        "async_discovered_service_info",
        return_value=[service_info],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return result


async def _manual_form_with_stale_cache(
    hass: HomeAssistant, service_info: MagicMock
) -> dict:
    """Open the manual form, then simulate its discovery cache changing."""
    original_schema = config_flow.BMxConfigFlow._manual_schema

    def clear_after_schema(
        flow: config_flow.BMxConfigFlow,
        defaults: dict[str, Any] | None = None,
    ) -> probatio.Schema:
        schema = original_schema(flow, defaults)
        flow._discovered_devices.clear()
        return schema

    with (
        patch.object(config_flow.BMxConfigFlow, "_manual_schema", clear_after_schema),
        patch.object(
            config_flow, "async_discovered_service_info", return_value=[service_info]
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    return result


async def _discovery_form(
    hass: HomeAssistant, service_info: MagicMock, validation: str = "valid_passive"
) -> dict:
    """Start Bluetooth discovery with a chosen protocol-validation result."""
    with patch.object(
        config_flow.BMxConfigFlow,
        "_async_validate_device",
        return_value=validation,
    ):
        return await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_BLUETOOTH},
            data=service_info,
        )


@pytest.mark.parametrize("validation", ["valid_passive", "valid_active"])
async def test_bluetooth_discovery(
    hass: HomeAssistant, service_info: MagicMock, validation: str
) -> None:
    """Confirmed passive and active devices produce unique config entries."""
    result = await _discovery_form(hass, service_info, validation)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert not flows[0]["context"].get("confirm_only", False)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_BATTERY_TYPE: DEFAULT_BATTERY_TYPE}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {}
    assert result["options"] == {CONF_BATTERY_TYPE: DEFAULT_BATTERY_TYPE}
    assert result["result"].unique_id == ADDRESS


@pytest.mark.parametrize(
    ("validation", "reason"),
    [("not_bm2", "not_supported"), ("cannot_validate", "cannot_validate")],
)
async def test_bluetooth_discovery_rejected(
    hass: HomeAssistant, service_info: MagicMock, validation: str, reason: str
) -> None:
    """Discovery only offers positively identified BM2 devices."""
    result = await _discovery_form(hass, service_info, validation)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_bluetooth_duplicate(
    hass: HomeAssistant, service_info: MagicMock
) -> None:
    """An already configured address cannot start another discovery flow."""
    MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS).add_to_hass(hass)
    with patch.object(config_flow.BMxConfigFlow, "_async_validate_device") as validate:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_BLUETOOTH},
            data=service_info,
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    validate.assert_not_called()


async def test_manual_device(hass: HomeAssistant, service_info: MagicMock) -> None:
    """A manually selected device must pass protocol validation."""
    result = await _manual_form(hass, service_info)
    with patch.object(
        config_flow.BMxConfigFlow,
        "_async_validate_device",
        return_value="valid_passive",
    ) as validate:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: ADDRESS, CONF_BATTERY_TYPE: DEFAULT_BATTERY_TYPE},
        )
    validate.assert_awaited_once()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ADDRESS: ADDRESS}
    assert result["options"] == {CONF_BATTERY_TYPE: DEFAULT_BATTERY_TYPE}
    assert result["result"].unique_id == ADDRESS


async def test_manual_unnamed_device_can_be_validated(
    hass: HomeAssistant, service_info: MagicMock
) -> None:
    """A genuine BM2 can be selected even without a recognised Bluetooth name."""
    service_info.name = ADDRESS
    result = await _manual_form(hass, service_info)
    with patch.object(
        config_flow.BMxConfigFlow,
        "_async_validate_device",
        return_value="valid_active",
    ) as validate:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: ADDRESS, CONF_BATTERY_TYPE: DEFAULT_BATTERY_TYPE},
        )
    validate.assert_awaited_once()
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("validation", "error"),
    [("not_bm2", "not_bm2"), ("cannot_validate", "cannot_validate")],
)
async def test_manual_validation_error_and_retry(
    hass: HomeAssistant, service_info: MagicMock, validation: str, error: str
) -> None:
    """Show a useful error and allow a second attempt on the same form."""
    result = await _manual_form(hass, service_info)
    with (
        patch.object(
            config_flow, "async_discovered_service_info", return_value=[service_info]
        ),
        patch.object(
            config_flow.BMxConfigFlow,
            "_async_validate_device",
            side_effect=[validation, "valid_passive"],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: ADDRESS, CONF_BATTERY_TYPE: DEFAULT_BATTERY_TYPE},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": error}
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: ADDRESS, CONF_BATTERY_TYPE: DEFAULT_BATTERY_TYPE},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_manual_without_devices(hass: HomeAssistant) -> None:
    """No visible devices yields a clear abort."""
    with patch.object(config_flow, "async_discovered_service_info", return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_manual_device_disappeared(
    hass: HomeAssistant, service_info: MagicMock
) -> None:
    """A device absent from both caches is not silently configured."""
    result = await _manual_form_with_stale_cache(hass, service_info)
    with patch.object(config_flow, "async_discovered_service_info", return_value=[]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: ADDRESS, CONF_BATTERY_TYPE: DEFAULT_BATTERY_TYPE},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_manual_device_reappears(
    hass: HomeAssistant, service_info: MagicMock
) -> None:
    """A selected device found by refreshing discovery can be configured."""
    result = await _manual_form_with_stale_cache(hass, service_info)
    with (
        patch.object(
            config_flow, "async_discovered_service_info", return_value=[service_info]
        ),
        patch.object(
            config_flow.BMxConfigFlow,
            "_async_validate_device",
            return_value="valid_passive",
        ) as validate,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: ADDRESS, CONF_BATTERY_TYPE: DEFAULT_BATTERY_TYPE},
        )
    validate.assert_awaited_once()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_manual_excludes_configured_devices(
    hass: HomeAssistant, service_info: MagicMock
) -> None:
    """An already configured address is omitted from manual discovery."""
    MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS).add_to_hass(hass)
    with patch.object(
        config_flow, "async_discovered_service_info", return_value=[service_info]
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_manual_known_name(hass: HomeAssistant, service_info: MagicMock) -> None:
    """Recognised names are offered with a BM2 title."""
    service_info.name = next(iter(BM_NAMES))
    result = await _manual_form(hass, service_info)
    assert result["type"] is FlowResultType.FORM


async def test_manual_duplicate(hass: HomeAssistant, service_info: MagicMock) -> None:
    """Manual selection rejects an address configured after opening the form."""
    result = await _manual_form(hass, service_info)
    MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS).add_to_hass(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ADDRESS: ADDRESS, CONF_BATTERY_TYPE: DEFAULT_BATTERY_TYPE},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_manual_custom_must_validate_device(
    hass: HomeAssistant, service_info: MagicMock
) -> None:
    """A custom chemistry cannot bypass device validation."""
    result = await _manual_form(hass, service_info)
    with (
        patch.object(
            config_flow.BMxConfigFlow,
            "_async_validate_device",
            return_value="not_bm2",
        ) as validate,
        patch.object(
            config_flow, "async_discovered_service_info", return_value=[service_info]
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: ADDRESS, CONF_BATTERY_TYPE: "Custom"},
        )
    validate.assert_awaited_once()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "not_bm2"}


async def test_manual_custom_details(
    hass: HomeAssistant, service_info: MagicMock
) -> None:
    """Manual custom setup keeps chemistry settings in entry options."""
    result = await _manual_form(hass, service_info)
    with patch.object(
        config_flow.BMxConfigFlow,
        "_async_validate_device",
        return_value="valid_active",
    ) as validate:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: ADDRESS, CONF_BATTERY_TYPE: "Custom"},
        )
    validate.assert_awaited_once()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "custom_battery_details"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CUSTOM_DETAILS.copy()
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ADDRESS: ADDRESS}
    assert result["options"][CONF_BATTERY_TYPE] == "Custom"
    assert result["options"][CONF_CUSTOM_NUMPY_VOLTS] == [11.0, 11.5, 12.3, 12.8]
    assert result["result"].unique_id == ADDRESS


async def test_bluetooth_custom_details(
    hass: HomeAssistant, service_info: MagicMock
) -> None:
    """A custom battery uses a second form and stores derived lookup values."""
    result = await _discovery_form(hass, service_info)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_BATTERY_TYPE: "Custom"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "custom_battery_details"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CUSTOM_DETAILS.copy()
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ADDRESS: ADDRESS}
    assert result["options"][CONF_BATTERY_TYPE] == "Custom"
    assert result["options"][CONF_CUSTOM_NUMPY_VOLTS] == [11.0, 11.5, 12.3, 12.8]
    assert result["options"][CONF_CUSTOM_NUMPY_PERCENT] == [0, 20, 50, 100]
    assert result["result"].unique_id == ADDRESS


async def test_custom_voltages_out_of_order(
    hass: HomeAssistant, service_info: MagicMock
) -> None:
    """Invalid custom thresholds keep the form open and can be corrected."""
    result = await _discovery_form(hass, service_info)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_BATTERY_TYPE: "Custom"}
    )
    invalid = {**CUSTOM_DETAILS, CONF_CUSTOM_LOW_VOLTAGE: 11.0}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], invalid)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "custom_voltages_not_in_order"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CUSTOM_DETAILS.copy()
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_regular(hass: HomeAssistant) -> None:
    """Saving ordinary options completes the flow."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, options={})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    options = {
        CONF_BATTERY_TYPE: DEFAULT_BATTERY_TYPE,
        CONF_RATE_LIMIT_MODE: DEFAULT_RATE_LIMIT_MODE,
        CONF_RATE_LIMIT: DEFAULT_RATE_LIMIT,
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], options
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == options


async def test_options_switch_from_custom(hass: HomeAssistant) -> None:
    """Changing to a standard chemistry removes obsolete custom thresholds."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ADDRESS,
        options={CONF_BATTERY_TYPE: "Custom", **CUSTOM_DETAILS},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    options = {
        CONF_BATTERY_TYPE: DEFAULT_BATTERY_TYPE,
        CONF_RATE_LIMIT_MODE: DEFAULT_RATE_LIMIT_MODE,
        CONF_RATE_LIMIT: DEFAULT_RATE_LIMIT,
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], options
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == options


async def test_options_custom_error_and_retry(hass: HomeAssistant) -> None:
    """Custom options merge both forms and recover from invalid thresholds."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, options={})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_BATTERY_TYPE: "Custom",
            CONF_RATE_LIMIT_MODE: DEFAULT_RATE_LIMIT_MODE,
            CONF_RATE_LIMIT: 12,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "custom_battery_details"
    invalid = {**CUSTOM_DETAILS, CONF_CUSTOM_LOW_VOLTAGE: 11.0}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], invalid
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "custom_voltages_not_in_order"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], CUSTOM_DETAILS.copy()
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_RATE_LIMIT] == 12
    assert result["data"][CONF_CUSTOM_NUMPY_VOLTS] == [11.0, 11.5, 12.3, 12.8]


@pytest.mark.parametrize(
    ("generation", "active_result", "expected"),
    [
        (BM2Generation.ENHANCED, None, "valid_passive"),
        (BM2Generation.LEGACY, None, "valid_passive"),
        (BM2Generation.UNKNOWN, True, "valid_active"),
        (BM2Generation.UNKNOWN, False, "not_bm2"),
    ],
)
async def test_protocol_validation(
    hass: HomeAssistant,
    service_info: MagicMock,
    generation: BM2Generation,
    active_result: bool | None,
    expected: str,
) -> None:
    """Prefer proven advertisements; otherwise validate the GATT protocol."""
    flow = config_flow.BMxConfigFlow()
    flow.hass = hass
    device = MagicMock()
    device.bm2_generation = generation
    device.async_validate_active = AsyncMock(return_value=active_result)
    ble_device = MagicMock()
    with (
        patch.object(protocol_validation, "DeviceData", return_value=device),
        patch.object(
            protocol_validation, "async_process_advertisements", new_callable=AsyncMock
        ) as listen,
        patch.object(
            protocol_validation,
            "async_ble_device_from_address",
            return_value=ble_device,
        ) as get_device,
    ):
        assert await flow._async_validate_device(service_info) == expected
    if generation is BM2Generation.UNKNOWN:
        listen.assert_awaited_once()
        get_device.assert_called_once_with(hass, ADDRESS, connectable=True)
        device.async_validate_active.assert_awaited_once_with(ble_device)
    else:
        listen.assert_not_awaited()
        get_device.assert_not_called()


@pytest.mark.parametrize(
    "active_path",
    [None, BleakError("Connection lost"), TimeoutError("Connection timed out")],
)
async def test_validation_cannot_connect(
    hass: HomeAssistant, service_info: MagicMock, active_path: object
) -> None:
    """No connectable path and connection errors are inconclusive."""
    flow = config_flow.BMxConfigFlow()
    flow.hass = hass
    device = MagicMock()
    device.bm2_generation = BM2Generation.UNKNOWN
    device.async_validate_active = AsyncMock(
        side_effect=active_path if isinstance(active_path, Exception) else None
    )
    with (
        patch.object(protocol_validation, "DeviceData", return_value=device),
        patch.object(
            protocol_validation,
            "async_process_advertisements",
            new_callable=AsyncMock,
            side_effect=TimeoutError,
        ),
        patch.object(
            protocol_validation,
            "async_ble_device_from_address",
            return_value=None if active_path is None else MagicMock(),
        ),
    ):
        assert await flow._async_validate_device(service_info) == "cannot_validate"


async def test_second_advertisement_proves_identity(
    hass: HomeAssistant, service_info: MagicMock
) -> None:
    """An alternating packet type can establish identity without a GATT read."""
    flow = config_flow.BMxConfigFlow()
    flow.hass = hass
    device = MagicMock()
    device.bm2_generation = BM2Generation.UNKNOWN
    calls = 0

    def check(_device: MagicMock, _service_info: MagicMock) -> bool:
        nonlocal calls
        if calls:
            device.bm2_generation = BM2Generation.ENHANCED
            return True
        calls += 1
        return False

    async def receive(
        _hass: HomeAssistant,
        callback: Callable[[BluetoothServiceInfoBleak], bool],
        _matcher: dict[str, object],
        _mode: BluetoothScanningMode,
        _timeout: float,
    ) -> None:
        assert callback(service_info)

    with (
        patch.object(protocol_validation, "DeviceData", return_value=device),
        patch.object(protocol_validation, "advertisement_is_bm2", side_effect=check),
        patch.object(
            protocol_validation, "async_process_advertisements", side_effect=receive
        ),
        patch.object(
            protocol_validation, "async_ble_device_from_address"
        ) as get_device,
    ):
        assert await flow._async_validate_device(service_info) == "valid_passive"
    get_device.assert_not_called()


@pytest.mark.usefixtures("mock_bluetooth")
@pytest.mark.parametrize("connectable", [False, True])
@pytest.mark.parametrize(
    ("local_name", "manufacturer_data"),
    [
        ("Battery Monitor", {}),
        ("Li Battery Monitor", {}),
        ("ZX-1689", {}),
        (
            None,
            {76: bytes.fromhex("0215655f83caae16a10a702e31f30d58dd82000000002d")},
        ),
    ],
    ids=["battery-monitor", "li-battery-monitor", "zx-1689", "manufacturer-data"],
)
async def test_bluetooth_matcher_discovery(
    hass: HomeAssistant,
    local_name: str | None,
    manufacturer_data: dict[int, bytes],
    connectable: bool,
) -> None:
    """Every generated matcher starts discovery through either scanner type."""
    device = generate_ble_device(ADDRESS, local_name)
    advertisement = generate_advertisement_data(
        local_name=local_name,
        manufacturer_data=manufacturer_data,
        rssi=-60,
    )
    with patch.object(
        config_flow.BMxConfigFlow,
        "_async_validate_device",
        return_value="valid_passive",
    ) as validate:
        await async_setup_with_default_adapter(hass)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        inject_advertisement_with_time_and_source_connectable(
            hass,
            device,
            advertisement,
            monotonic(),
            "passive-test-proxy" if not connectable else "active-test-proxy",
            connectable,
        )
        await hass.async_block_till_done(wait_background_tasks=True)
        flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        assert len(flows) == 1
        assert flows[0]["context"]["source"] == SOURCE_BLUETOOTH
        assert flows[0]["context"]["unique_id"] == ADDRESS
        assert not flows[0]["context"].get("confirm_only", False)
        validate.assert_awaited_once()
        discovered_info = validate.call_args.args[0]
        assert discovered_info.address == ADDRESS
        assert discovered_info.connectable is connectable
        result = await hass.config_entries.flow.async_configure(flows[0]["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "bluetooth_confirm"
        assert result["errors"] is None


@pytest.mark.parametrize("error", [AttributeError, TypeError])
async def test_validation_programming_error_propagates(
    hass: HomeAssistant,
    service_info: MagicMock,
    error: type[Exception],
) -> None:
    """Programming defects must not be converted into a validation retry."""
    device = MagicMock()
    device.bm2_generation = BM2Generation.UNKNOWN
    device.async_validate_active = AsyncMock(side_effect=error("Unexpected defect"))
    with (
        patch.object(protocol_validation, "DeviceData", return_value=device),
        patch.object(
            protocol_validation,
            "async_process_advertisements",
            new_callable=AsyncMock,
            side_effect=TimeoutError,
        ),
        patch.object(
            protocol_validation,
            "async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        pytest.raises(error, match="Unexpected defect"),
    ):
        await protocol_validation.async_validate_device(hass, service_info)
