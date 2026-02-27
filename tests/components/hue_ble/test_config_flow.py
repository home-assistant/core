"""Test the Hue BLE config flow."""

from unittest.mock import AsyncMock, PropertyMock, patch

from habluetooth import BluetoothServiceInfoBleak
from HueBLE import ConnectionError, HueBleError, PairingError
import pytest

from homeassistant.components.hue_ble.config_flow import Error
from homeassistant.components.hue_ble.const import (
    DOMAIN,
    URL_FACTORY_RESET,
    URL_PAIRING_MODE,
)
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr

from . import (
    HUE_BLE_SERVICE_INFO,
    NOT_HUE_BLE_DISCOVERY_INFO,
    TEST_DEVICE_MAC,
    TEST_DEVICE_NAME,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import BLEDevice, generate_ble_device

AUTH_ERROR = ConnectionError()
AUTH_ERROR.__cause__ = PairingError()


async def test_user_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user form."""

    with patch(
        "homeassistant.components.hue_ble.config_flow.bluetooth.async_discovered_service_info",
        return_value=[NOT_HUE_BLE_DISCOVERY_INFO, HUE_BLE_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["data_schema"].schema[CONF_MAC].container == {
        HUE_BLE_SERVICE_INFO.address: (
            f"{HUE_BLE_SERVICE_INFO.name} ({HUE_BLE_SERVICE_INFO.address})"
        ),
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_MAC: HUE_BLE_SERVICE_INFO.address},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {
        CONF_NAME: TEST_DEVICE_NAME,
        CONF_MAC: TEST_DEVICE_MAC,
        "url_pairing_mode": URL_PAIRING_MODE,
        "url_factory_reset": URL_FACTORY_RESET,
    }

    with (
        patch(
            "homeassistant.components.hue_ble.config_flow.async_ble_device_from_address",
            return_value=generate_ble_device(TEST_DEVICE_NAME, TEST_DEVICE_MAC),
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.async_scanner_count",
            return_value=1,
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.HueBleLight.connect",
            side_effect=[True],
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.HueBleLight.poll_state",
            side_effect=[True],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_DEVICE_NAME
    assert result["result"].unique_id == dr.format_mac(TEST_DEVICE_MAC)
    assert result["result"].data == {}

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize("discovery_info", [[NOT_HUE_BLE_DISCOVERY_INFO], []])
async def test_user_form_no_device(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    discovery_info: list[BluetoothServiceInfoBleak],
) -> None:
    """Test user form with no devices."""

    with patch(
        "homeassistant.components.hue_ble.config_flow.bluetooth.async_discovered_service_info",
        return_value=discovery_info,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


@pytest.mark.parametrize(
    (
        "mock_return_device",
        "mock_scanner_count",
        "mock_connect",
        "mock_support_on_off",
        "mock_poll_state",
        "error",
    ),
    [
        (
            None,
            0,
            None,
            True,
            None,
            Error.NO_SCANNERS,
        ),
        (
            None,
            1,
            None,
            True,
            None,
            Error.NOT_FOUND,
        ),
        (
            generate_ble_device(TEST_DEVICE_NAME, TEST_DEVICE_MAC),
            1,
            AUTH_ERROR,
            True,
            None,
            Error.INVALID_AUTH,
        ),
        (
            generate_ble_device(TEST_DEVICE_NAME, TEST_DEVICE_MAC),
            1,
            ConnectionError,
            True,
            None,
            Error.CANNOT_CONNECT,
        ),
        (
            generate_ble_device(TEST_DEVICE_NAME, TEST_DEVICE_MAC),
            1,
            None,
            False,
            None,
            Error.NOT_SUPPORTED,
        ),
        (
            generate_ble_device(TEST_DEVICE_NAME, TEST_DEVICE_MAC),
            1,
            None,
            True,
            HueBleError,
            Error.UNKNOWN,
        ),
        (
            generate_ble_device(TEST_DEVICE_NAME, TEST_DEVICE_MAC),
            1,
            HueBleError,
            None,
            None,
            Error.UNKNOWN,
        ),
    ],
    ids=[
        "no_scanners",
        "not_found",
        "invalid_auth",
        "cannot_connect",
        "not_supported",
        "cannot_poll",
        "unknown",
    ],
)
async def test_user_form_exception(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_return_device: BLEDevice | None,
    mock_scanner_count: int,
    mock_connect: Exception | None,
    mock_support_on_off: bool,
    mock_poll_state: Exception | None,
    error: Error,
) -> None:
    """Test user form with errors."""

    with patch(
        "homeassistant.components.hue_ble.config_flow.bluetooth.async_discovered_service_info",
        return_value=[NOT_HUE_BLE_DISCOVERY_INFO, HUE_BLE_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["data_schema"].schema[CONF_MAC].container == {
        HUE_BLE_SERVICE_INFO.address: (
            f"{HUE_BLE_SERVICE_INFO.name} ({HUE_BLE_SERVICE_INFO.address})"
        ),
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_MAC: HUE_BLE_SERVICE_INFO.address},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    with (
        patch(
            "homeassistant.components.hue_ble.config_flow.async_ble_device_from_address",
            return_value=mock_return_device,
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.async_scanner_count",
            return_value=mock_scanner_count,
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.HueBleLight.connect",
            side_effect=[mock_connect],
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.HueBleLight.supports_on_off",
            new_callable=PropertyMock,
            return_value=mock_support_on_off,
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.HueBleLight.poll_state",
            side_effect=[mock_poll_state],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": error.value}

    with (
        patch(
            "homeassistant.components.hue_ble.config_flow.async_ble_device_from_address",
            return_value=generate_ble_device(TEST_DEVICE_NAME, TEST_DEVICE_MAC),
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.async_scanner_count",
            return_value=1,
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.HueBleLight.connect",
            side_effect=[True],
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.HueBleLight.poll_state",
            side_effect=[True],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_bluetooth_discovery_aborts(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test bluetooth form aborts."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=HUE_BLE_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "discovery_unsupported"


async def test_bluetooth_form_exception_already_set_up(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test bluetooth discovery form when device is already set up."""

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=HUE_BLE_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "discovery_unsupported"


async def test_user_form_exception_already_set_up(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test user form when device is already set up."""

    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.hue_ble.config_flow.bluetooth.async_discovered_service_info",
        return_value=[NOT_HUE_BLE_DISCOVERY_INFO, HUE_BLE_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["data_schema"].schema[CONF_MAC].container == {
        HUE_BLE_SERVICE_INFO.address: (
            f"{HUE_BLE_SERVICE_INFO.name} ({HUE_BLE_SERVICE_INFO.address})"
        ),
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_MAC: HUE_BLE_SERVICE_INFO.address},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
