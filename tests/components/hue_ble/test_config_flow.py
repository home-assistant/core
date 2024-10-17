"""Test the Hue BLE config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.hue_ble.config_flow import (
    CannotConnect,
    InvalidAuth,
    NotFound,
    ScannerNotAvailable,
)
from homeassistant.components.hue_ble.const import DOMAIN, URL_PAIRING_MODE
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr

from . import HUE_BLE_SERVICE_INFO, TEST_DEVICE_MAC, TEST_DEVICE_NAME

from tests.components.bluetooth import generate_ble_device


@pytest.mark.parametrize(
    (
        "return_device_result",
        "scanner_count_result",
        "connect_result",
        "authenticated_result",
        "connected_result",
        "poll_state_result",
        "expected_error",
    ),
    [
        (
            generate_ble_device(TEST_DEVICE_NAME, TEST_DEVICE_MAC),
            1,
            True,
            True,
            True,
            (True, []),
            None,
        ),
        (
            None,
            0,
            True,
            True,
            True,
            (True, []),
            "no_scanners",
        ),
        (
            None,
            1,
            True,
            True,
            True,
            (True, []),
            "not_found",
        ),
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
            None,
            True,
            (True, []),
            None,
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
            (True, ["Error :P"]),
            "cannot_connect",
        ),
    ],
    ids=[
        "good_data",
        "no_scanners",
        "not_found",
        "invalid_auth",
        "unknown_auth_status",
        "cannot_connect",
        "failed_poll",
    ],
)
async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    return_device_result,
    scanner_count_result,
    connect_result,
    authenticated_result,
    connected_result,
    poll_state_result,
    expected_error,
) -> None:
    """Test form with data."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    with (
        patch(
            "homeassistant.components.hue_ble.config_flow.async_ble_device_from_address",
            return_value=return_device_result,
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.async_scanner_count",
            return_value=scanner_count_result,
        ),
        patch(
            "homeassistant.components.hue_ble.config_flow.HueBleLight",
            autospec=True,
            authenticated=authenticated_result,
            connected=connected_result,
        ) as mock_obj,
    ):
        client = mock_obj.return_value
        client.connect.return_value = connect_result
        client.authenticated = authenticated_result
        client.connected = connected_result
        client.poll_state.return_value = poll_state_result

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: TEST_DEVICE_NAME, CONF_MAC: TEST_DEVICE_MAC},
        )
        await hass.async_block_till_done()

    if expected_error is not None:
        assert result["type"] is FlowResultType.FORM
        assert result["description_placeholders"] == {
            "url_pairing_mode": URL_PAIRING_MODE,
        }
        assert result["errors"] == {"base": expected_error}

        with patch(
            "homeassistant.components.hue_ble.config_flow.validate_input",
            return_value=True,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_NAME: TEST_DEVICE_NAME, CONF_MAC: TEST_DEVICE_MAC},
            )
            await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_DEVICE_NAME
    assert result["result"].unique_id == dr.format_mac(TEST_DEVICE_MAC)
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_unknown(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test form when unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: TEST_DEVICE_NAME, CONF_MAC: TEST_DEVICE_MAC},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: TEST_DEVICE_NAME, CONF_MAC: TEST_DEVICE_MAC},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_DEVICE_NAME
    assert result["result"].unique_id == dr.format_mac(TEST_DEVICE_MAC)
    assert len(mock_setup_entry.mock_calls) == 1


async def test_bluetooth_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test bluetooth discovery form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=HUE_BLE_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {
        "name": TEST_DEVICE_NAME,
        "url_pairing_mode": URL_PAIRING_MODE,
    }

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_DEVICE_NAME
    assert result["result"].unique_id == dr.format_mac(TEST_DEVICE_MAC)

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "error_message"),
    [
        (CannotConnect, "cannot_connect"),
        (InvalidAuth, "invalid_auth"),
        (ScannerNotAvailable, "no_scanners"),
        (NotFound, "not_found"),
        (Exception, "unknown"),
    ],
    ids=[
        "cannot_connect",
        "device_not_authenticated",
        "scanner_not_avaliable",
        "device_not_found",
        "unknown",
    ],
)
async def test_bluetooth_form_exception(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, side_effect, error_message
) -> None:
    """Test bluetooth discovery form with errors."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=HUE_BLE_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_message}

    with patch(
        "homeassistant.components.hue_ble.config_flow.validate_input",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_DEVICE_NAME
    assert result["result"].unique_id == dr.format_mac(TEST_DEVICE_MAC)

    assert len(mock_setup_entry.mock_calls) == 1
