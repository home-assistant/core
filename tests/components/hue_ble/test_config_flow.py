"""Test the Hue BLE config flow."""

from unittest.mock import AsyncMock, PropertyMock, patch

import pytest

from homeassistant.components.hue_ble.const import DOMAIN, URL_PAIRING_MODE
from homeassistant.config_entries import SOURCE_BLUETOOTH
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr

from . import HUE_BLE_SERVICE_INFO, TEST_DEVICE_MAC, TEST_DEVICE_NAME

from tests.components.bluetooth import BLEDevice, generate_ble_device


@pytest.mark.parametrize(
    (
        "mock_return_device",
        "mock_scanner_count",
        "mock_connect",
        "mock_authenticated",
        "mock_connected",
        "mock_poll_state",
    ),
    [
        (
            generate_ble_device(TEST_DEVICE_NAME, TEST_DEVICE_MAC),
            1,
            True,
            True,
            True,
            (True, []),
        ),
        (
            generate_ble_device(TEST_DEVICE_NAME, TEST_DEVICE_MAC),
            1,
            True,
            None,
            True,
            (True, []),
        ),
    ],
    ids=[
        "normal",
        "unknown_auth",
    ],
)
async def test_bluetooth_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_return_device: BLEDevice | None,
    mock_scanner_count: int,
    mock_connect: Exception | bool,
    mock_authenticated: bool | None,
    mock_connected: bool,
    mock_poll_state: Exception | tuple[bool, list[Exception]],
) -> None:
    """Test bluetooth discovery form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=HUE_BLE_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {
        CONF_NAME: TEST_DEVICE_NAME,
        CONF_MAC: TEST_DEVICE_MAC,
        "url_pairing_mode": URL_PAIRING_MODE,
    }

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
            "homeassistant.components.hue_ble.config_flow.HueBleLight.poll_state",
            side_effect=[mock_poll_state],
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.HueBleLight.connected",
            new_callable=PropertyMock,
            return_value=mock_connected,
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.HueBleLight.authenticated",
            new_callable=PropertyMock,
            return_value=mock_authenticated,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_DEVICE_NAME
    assert result["result"].unique_id == dr.format_mac(TEST_DEVICE_MAC)
    assert result["result"].data == {}

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    (
        "mock_return_device",
        "mock_scanner_count",
        "mock_connect",
        "mock_authenticated",
        "mock_connected",
        "mock_poll_state",
        "error_message",
    ),
    [
        (None, 0, True, True, True, (True, []), "no_scanners"),
        (None, 1, True, True, True, (True, []), "not_found"),
        (
            generate_ble_device(TEST_DEVICE_NAME, TEST_DEVICE_MAC),
            1,
            True,
            False,
            True,
            (True, []),
            "invalid_auth",
        ),
        (
            generate_ble_device(TEST_DEVICE_NAME, TEST_DEVICE_MAC),
            1,
            True,
            True,
            False,
            (True, []),
            "cannot_connect",
        ),
        (
            generate_ble_device(TEST_DEVICE_NAME, TEST_DEVICE_MAC),
            1,
            True,
            True,
            True,
            (True, ["ERROR!"]),
            "cannot_connect",
        ),
        (
            generate_ble_device(TEST_DEVICE_NAME, TEST_DEVICE_MAC),
            1,
            Exception,
            None,
            True,
            (True, []),
            "unknown",
        ),
    ],
    ids=[
        "no_scanners",
        "not_found",
        "invalid_auth",
        "cannot_connect",
        "cannot_poll",
        "unknown",
    ],
)
async def test_bluetooth_form_exception(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_return_device: BLEDevice | None,
    mock_scanner_count: int,
    mock_connect: Exception | bool,
    mock_authenticated: bool | None,
    mock_connected: bool,
    mock_poll_state: Exception | tuple[bool, list[Exception]],
    error_message: str,
) -> None:
    """Test bluetooth discovery form with errors."""

    form_init = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=HUE_BLE_SERVICE_INFO,
    )
    assert form_init["type"] is FlowResultType.FORM
    assert form_init["step_id"] == "confirm"

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
            "homeassistant.components.hue_ble.config_flow.HueBleLight.poll_state",
            side_effect=[mock_poll_state],
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.HueBleLight.connected",
            new_callable=PropertyMock,
            return_value=mock_connected,
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.HueBleLight.authenticated",
            new_callable=PropertyMock,
            return_value=mock_authenticated,
        ),
    ):
        form_confirm = await hass.config_entries.flow.async_configure(
            form_init["flow_id"],
            {},
        )
        await hass.async_block_till_done()

        assert form_confirm["type"] is FlowResultType.FORM
        assert form_confirm["errors"] == {"base": error_message}
