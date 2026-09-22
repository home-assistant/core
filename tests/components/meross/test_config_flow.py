"""Test the Meross Bluetooth config flow."""

from unittest.mock import AsyncMock, patch

from home_assistant_bluetooth import BluetoothServiceInfoBleak
from meross_ble import MerossBLEError

from homeassistant import config_entries
from homeassistant.components.meross.const import DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    MEROSS_MS120_ADDRESS,
    MEROSS_MS120_SERVICE_INFO,
    MEROSS_MS220_SERVICE_INFO,
    NOT_MEROSS_SERVICE_INFO,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_advertisement_data, generate_ble_device


async def test_bluetooth_discovery(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth with a valid device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=MEROSS_MS120_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    with (
        patch(
            "homeassistant.components.meross.config_flow.bluetooth.async_ble_device_from_address",
            return_value=MEROSS_MS120_SERVICE_INFO.device,
        ),
        patch(
            "homeassistant.components.meross.config_flow.create_device"
        ) as mock_create,
        patch(
            "homeassistant.components.meross.async_setup_entry",
            return_value=True,
        ),
    ):
        mock_create.return_value.identify = AsyncMock(return_value=True)
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Meross MS120"
    assert result2["data"][CONF_ADDRESS] == MEROSS_MS120_ADDRESS
    assert result2["data"][CONF_MODEL] == "ms120"
    assert result2["result"].unique_id == "aabbccddeeff"


async def test_bluetooth_identify_failed(hass: HomeAssistant) -> None:
    """Test bluetooth confirm surfaces Identify failures."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=MEROSS_MS120_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    with (
        patch(
            "homeassistant.components.meross.config_flow.bluetooth.async_ble_device_from_address",
            return_value=MEROSS_MS120_SERVICE_INFO.device,
        ),
        patch(
            "homeassistant.components.meross.config_flow.create_device"
        ) as mock_create,
    ):
        mock_create.return_value.identify = AsyncMock(
            side_effect=MerossBLEError("identify failed")
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "bluetooth_confirm"
    assert result2["errors"] == {"base": "identify_failed"}


async def test_bluetooth_identify_missing_device(hass: HomeAssistant) -> None:
    """Test Identify fails when the BLE device leaves the cache."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=MEROSS_MS120_SERVICE_INFO,
    )

    with patch(
        "homeassistant.components.meross.config_flow.bluetooth.async_ble_device_from_address",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "identify_failed"}


async def test_bluetooth_not_supported(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth with an unsupported device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=NOT_MEROSS_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_bluetooth_already_configured(hass: HomeAssistant) -> None:
    """Test we abort if the device is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aabbccddeeff",
        data={
            CONF_ADDRESS: MEROSS_MS120_ADDRESS,
            CONF_MODEL: "ms120",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=MEROSS_MS120_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_no_adapter(hass: HomeAssistant) -> None:
    """Test manual setup aborts without a Bluetooth adapter."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_bluetooth_adapter"


async def test_user_no_devices_found(hass: HomeAssistant) -> None:
    """Test manual setup aborts when nothing is discovered."""
    with (
        patch(
            "homeassistant.components.meross.config_flow.bluetooth.async_request_active_scan"
        ),
        patch(
            "homeassistant.components.meross.config_flow.bluetooth.async_scanner_count",
            return_value=1,
        ),
        patch(
            "homeassistant.components.meross.config_flow.async_discovered_service_info",
            return_value=[],
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_single_device(hass: HomeAssistant) -> None:
    """Test manual setup with a single discovered device."""
    with (
        patch(
            "homeassistant.components.meross.config_flow.bluetooth.async_request_active_scan"
        ),
        patch(
            "homeassistant.components.meross.config_flow.bluetooth.async_scanner_count",
            return_value=1,
        ),
        patch(
            "homeassistant.components.meross.config_flow.async_discovered_service_info",
            return_value=[MEROSS_MS120_SERVICE_INFO],
        ),
        patch(
            "homeassistant.components.meross.config_flow.bluetooth.async_ble_device_from_address",
            return_value=MEROSS_MS120_SERVICE_INFO.device,
        ),
        patch(
            "homeassistant.components.meross.config_flow.create_device"
        ) as mock_create,
        patch(
            "homeassistant.components.meross.async_setup_entry",
            return_value=True,
        ),
    ):
        mock_create.return_value.identify = AsyncMock(return_value=True)
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "bluetooth_confirm"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Meross MS120"
    assert result2["data"][CONF_ADDRESS] == MEROSS_MS120_ADDRESS
    assert result2["data"][CONF_MODEL] == "ms120"


async def test_user_multiple_devices(hass: HomeAssistant) -> None:
    """Test manual setup asks the user to pick among matches."""
    second = BluetoothServiceInfoBleak(
        name="Meross-MS120-0002",
        address="AA:BB:CC:DD:00:02",
        device=generate_ble_device("AA:BB:CC:DD:00:02", "Meross-MS120-0002"),
        rssi=-60,
        manufacturer_data={},
        service_data=MEROSS_MS120_SERVICE_INFO.service_data,
        service_uuids=[],
        source="local",
        advertisement=generate_advertisement_data(
            local_name="Meross-MS120-0002",
            service_data=MEROSS_MS120_SERVICE_INFO.service_data,
        ),
        time=0,
        connectable=True,
        tx_power=-127,
    )

    with (
        patch(
            "homeassistant.components.meross.config_flow.bluetooth.async_request_active_scan"
        ),
        patch(
            "homeassistant.components.meross.config_flow.bluetooth.async_scanner_count",
            return_value=1,
        ),
        patch(
            "homeassistant.components.meross.config_flow.async_discovered_service_info",
            return_value=[MEROSS_MS120_SERVICE_INFO, second],
        ),
        patch(
            "homeassistant.components.meross.config_flow.bluetooth.async_ble_device_from_address",
            return_value=MEROSS_MS120_SERVICE_INFO.device,
        ),
        patch(
            "homeassistant.components.meross.config_flow.create_device"
        ) as mock_create,
        patch(
            "homeassistant.components.meross.async_setup_entry",
            return_value=True,
        ),
    ):
        mock_create.return_value.identify = AsyncMock(return_value=True)
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_ADDRESS: MEROSS_MS120_ADDRESS},
        )
        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "bluetooth_confirm"

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            user_input={},
        )

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["data"][CONF_ADDRESS] == MEROSS_MS120_ADDRESS


async def test_user_lists_all_meross_models(hass: HomeAssistant) -> None:
    """Test manual setup lists every discovered Meross model."""
    with (
        patch(
            "homeassistant.components.meross.config_flow.bluetooth.async_request_active_scan"
        ),
        patch(
            "homeassistant.components.meross.config_flow.bluetooth.async_scanner_count",
            return_value=1,
        ),
        patch(
            "homeassistant.components.meross.config_flow.async_discovered_service_info",
            return_value=[MEROSS_MS120_SERVICE_INFO, MEROSS_MS220_SERVICE_INFO],
        ),
        patch(
            "homeassistant.components.meross.config_flow.bluetooth.async_ble_device_from_address",
            return_value=MEROSS_MS220_SERVICE_INFO.device,
        ),
        patch(
            "homeassistant.components.meross.config_flow.create_device"
        ) as mock_create,
        patch(
            "homeassistant.components.meross.async_setup_entry",
            return_value=True,
        ),
    ):
        mock_create.return_value.identify = AsyncMock(return_value=True)
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_ADDRESS: MEROSS_MS220_SERVICE_INFO.address},
        )
        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "bluetooth_confirm"

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            user_input={},
        )

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["data"][CONF_MODEL] == "ms220"


async def test_user_already_configured(hass: HomeAssistant) -> None:
    """Test manual setup aborts when the only match is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aabbccddeeff",
        data={
            CONF_ADDRESS: MEROSS_MS120_ADDRESS,
            CONF_MODEL: "ms120",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.meross.config_flow.bluetooth.async_request_active_scan"
        ),
        patch(
            "homeassistant.components.meross.config_flow.bluetooth.async_scanner_count",
            return_value=1,
        ),
        patch(
            "homeassistant.components.meross.config_flow.async_discovered_service_info",
            return_value=[MEROSS_MS120_SERVICE_INFO],
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
