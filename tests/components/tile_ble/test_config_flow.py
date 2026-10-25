"""Tests for the Tile BLE config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.bluetooth import inject_bluetooth_service_info
from pytile.errors import InvalidAuthError, TileError

from homeassistant.components.tile_ble.const import CONF_AUTH_KEY, CONF_TILE, DOMAIN
from homeassistant.components.tile_ble.toa import (
    TileBleAuthenticationError,
    TileBleConnectionError,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ADDRESS, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from . import (
    AUTH_KEY,
    NEAR_TILE_SERVICE_INFO,
    NOT_TILE_SERVICE_INFO,
    TILE_ADDRESS,
    TILE_SERVICE_INFO,
)

ACCOUNT_INPUT = {CONF_USERNAME: "user@host.com", CONF_PASSWORD: "password"}
WALLET_UUID = "19264d2dffdbca32"


async def _start_flow_at_account_step(hass: HomeAssistant) -> FlowResult:
    """Pick the Tile over Bluetooth and return the account step."""
    inject_bluetooth_service_info(hass, TILE_SERVICE_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: TILE_ADDRESS}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "account"
    return result


@pytest.mark.usefixtures("mock_setup_entry", "mock_pytile")
async def test_user_flow(hass: HomeAssistant, mock_tile_ble_device: MagicMock) -> None:
    """Test the full flow, with the closest Tile listed first."""
    for service_info in (
        TILE_SERVICE_INFO,
        NOT_TILE_SERVICE_INFO,
        NEAR_TILE_SERVICE_INFO,
    ):
        inject_bluetooth_service_info(hass, service_info)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert list(result["data_schema"].schema[CONF_ADDRESS].container.items()) == [
        ("AA:BB:CC:DD:EE:11", "Tile (AA:BB:CC:DD:EE:11, -40 dBm)"),
        (TILE_ADDRESS, "Tile (AA:BB:CC:DD:EE:FF, -60 dBm)"),
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: TILE_ADDRESS}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "account"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ACCOUNT_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "tile"
    assert result["data_schema"].schema[CONF_TILE].container == {
        WALLET_UUID: "Wallet",
        "5176d2dffdbca32a": "Keys",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TILE: WALLET_UUID}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Wallet"
    assert result["data"] == {CONF_AUTH_KEY: AUTH_KEY}
    assert result["result"].unique_id == TILE_ADDRESS

    ble_device, auth_key = mock_tile_ble_device.call_args.args
    assert ble_device.address == TILE_ADDRESS
    assert auth_key == AUTH_KEY
    mock_tile_ble_device.return_value.async_authenticate.assert_awaited_once()


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        pytest.param(InvalidAuthError, "invalid_auth", id="invalid_auth"),
        pytest.param(TileError, "cannot_connect", id="cannot_connect"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry", "mock_tile_ble_device")
async def test_account_errors(
    hass: HomeAssistant,
    mock_pytile: AsyncMock,
    exception: type[Exception],
    error: str,
) -> None:
    """Test logging in to the Tile account can recover from errors."""
    result = await _start_flow_at_account_step(hass)

    mock_pytile.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ACCOUNT_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "account"
    assert result["errors"] == {"base": error}

    mock_pytile.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ACCOUNT_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "tile"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TILE: WALLET_UUID}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_account_without_tiles(
    hass: HomeAssistant, mock_pytile: AsyncMock
) -> None:
    """Test the flow aborts when the account has no Tiles with a key."""
    result = await _start_flow_at_account_step(hass)

    mock_pytile.return_value.async_get_tiles.return_value = {}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ACCOUNT_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_tiles"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        pytest.param(TileBleAuthenticationError, "wrong_tile", id="wrong_tile"),
        pytest.param(TileBleConnectionError, "cannot_connect", id="cannot_connect"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry", "mock_pytile")
async def test_tile_errors(
    hass: HomeAssistant,
    mock_tile_ble_device: MagicMock,
    exception: type[Exception],
    error: str,
) -> None:
    """Test checking the key over Bluetooth can recover from errors."""
    result = await _start_flow_at_account_step(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ACCOUNT_INPUT
    )

    mock_tile_ble_device.return_value.async_authenticate.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TILE: WALLET_UUID}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "tile"
    assert result["errors"] == {"base": error}

    mock_tile_ble_device.return_value.async_authenticate.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TILE: WALLET_UUID}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry", "mock_pytile")
async def test_tile_not_connectable(
    hass: HomeAssistant, mock_tile_ble_device: MagicMock
) -> None:
    """Test the Tile cannot be connected to when checking the key."""
    result = await _start_flow_at_account_step(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ACCOUNT_INPUT
    )

    with patch(
        "homeassistant.components.tile_ble.config_flow.async_ble_device_from_address",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TILE: WALLET_UUID}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    mock_tile_ble_device.assert_not_called()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TILE: WALLET_UUID}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    "service_infos",
    [
        pytest.param([], id="nothing_seen"),
        pytest.param([NOT_TILE_SERVICE_INFO], id="no_tiles_seen"),
    ],
)
async def test_user_flow_no_devices(
    hass: HomeAssistant, service_infos: list[BluetoothServiceInfo]
) -> None:
    """Test the flow aborts when no Tiles are seen."""
    for service_info in service_infos:
        inject_bluetooth_service_info(hass, service_info)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_flow_skips_configured_tiles(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test Tiles that are already set up are not offered again."""
    mock_config_entry.add_to_hass(hass)
    inject_bluetooth_service_info(hass, TILE_SERVICE_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a Tile set up while the form was open is not added twice."""
    inject_bluetooth_service_info(hass, TILE_SERVICE_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: TILE_ADDRESS}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
