"""Tests for the Tile BLE config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.bluetooth import inject_bluetooth_service_info
from pytile.errors import InvalidAuthError, TileError
from tile_ble import TileBleAuthenticationError, TileBleConnectionError

from homeassistant.components.tile_ble.const import CONF_AUTH_KEY, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ADDRESS, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from . import (
    AUTH_KEY,
    NEAR_TILE_SERVICE_INFO,
    NOT_TILE_SERVICE_INFO,
    OTHER_AUTH_KEY,
    TILE_ADDRESS,
    TILE_SERVICE_INFO,
)

ACCOUNT_INPUT = {CONF_USERNAME: "user@host.com", CONF_PASSWORD: "password"}
UNMATCHED_ADDRESS = NEAR_TILE_SERVICE_INFO.address


async def _log_in(hass: HomeAssistant) -> FlowResult:
    """Log in to the Tile account and return the device step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ACCOUNT_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device"
    return result


@pytest.mark.usefixtures("mock_setup_entry", "mock_pytile")
async def test_user_flow(
    hass: HomeAssistant,
    mock_tile_ble_device: MagicMock,
    mock_read_tile_id: AsyncMock,
) -> None:
    """Test setting up a Tile that is matched to the account by its address."""
    for service_info in (
        TILE_SERVICE_INFO,
        NOT_TILE_SERVICE_INFO,
        NEAR_TILE_SERVICE_INFO,
    ):
        inject_bluetooth_service_info(hass, service_info)

    result = await _log_in(hass)
    # Tiles from the account come first, even when another Tile is closer.
    assert list(result["data_schema"].schema[CONF_ADDRESS].container.items()) == [
        (TILE_ADDRESS, "Wallet (AA:BB:CC:DD:EE:FF)"),
        (UNMATCHED_ADDRESS, "AA:BB:CC:DD:EE:11 (-40 dBm)"),
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: TILE_ADDRESS}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Wallet"
    assert result["data"] == {CONF_AUTH_KEY: AUTH_KEY}
    assert result["result"].unique_id == TILE_ADDRESS

    ble_device, auth_key = mock_tile_ble_device.call_args.args
    assert ble_device.address == TILE_ADDRESS
    assert auth_key == AUTH_KEY
    mock_tile_ble_device.return_value.async_authenticate.assert_awaited_once()
    mock_read_tile_id.assert_not_called()


@pytest.mark.usefixtures("mock_setup_entry", "mock_pytile")
async def test_user_flow_unmatched_tile(
    hass: HomeAssistant,
    mock_tile_ble_device: MagicMock,
    mock_read_tile_id: AsyncMock,
) -> None:
    """Test setting up a Tile that is identified by reading its Tile ID."""
    inject_bluetooth_service_info(hass, NEAR_TILE_SERVICE_INFO)

    result = await _log_in(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: UNMATCHED_ADDRESS}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Keys"
    assert result["data"] == {CONF_AUTH_KEY: OTHER_AUTH_KEY}
    assert result["result"].unique_id == UNMATCHED_ADDRESS

    assert mock_read_tile_id.call_args.args[0].address == UNMATCHED_ADDRESS
    assert mock_tile_ble_device.call_args.args[1] == OTHER_AUTH_KEY


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        pytest.param(InvalidAuthError, "invalid_auth", id="invalid_auth"),
        pytest.param(TileError, "cannot_connect", id="cannot_connect"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry", "mock_tile_ble_device")
async def test_user_errors(
    hass: HomeAssistant,
    mock_pytile: AsyncMock,
    exception: type[Exception],
    error: str,
) -> None:
    """Test logging in to the Tile account can recover from errors."""
    inject_bluetooth_service_info(hass, TILE_SERVICE_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_pytile.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ACCOUNT_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    mock_pytile.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ACCOUNT_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: TILE_ADDRESS}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_account_without_tiles(
    hass: HomeAssistant, mock_pytile: AsyncMock
) -> None:
    """Test the flow aborts when the account has no Tiles with a key."""
    mock_pytile.return_value.async_get_tiles.return_value = {}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
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
async def test_authenticate_errors(
    hass: HomeAssistant,
    mock_tile_ble_device: MagicMock,
    exception: type[Exception],
    error: str,
) -> None:
    """Test checking the key over Bluetooth can recover from errors."""
    inject_bluetooth_service_info(hass, TILE_SERVICE_INFO)
    result = await _log_in(hass)

    mock_tile_ble_device.return_value.async_authenticate.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: TILE_ADDRESS}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device"
    assert result["errors"] == {"base": error}

    mock_tile_ble_device.return_value.async_authenticate.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: TILE_ADDRESS}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(TileBleConnectionError, "cannot_connect", id="cannot_connect"),
        pytest.param(["0000000000000000"], "unknown_tile", id="unknown_tile"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry", "mock_pytile", "mock_tile_ble_device")
async def test_read_tile_id_errors(
    hass: HomeAssistant,
    mock_read_tile_id: AsyncMock,
    side_effect: type[Exception] | list[str],
    error: str,
) -> None:
    """Test identifying an unmatched Tile can recover from errors."""
    inject_bluetooth_service_info(hass, TILE_SERVICE_INFO)
    inject_bluetooth_service_info(hass, NEAR_TILE_SERVICE_INFO)
    result = await _log_in(hass)

    mock_read_tile_id.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: UNMATCHED_ADDRESS}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device"
    assert result["errors"] == {"base": error}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: TILE_ADDRESS}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry", "mock_pytile")
async def test_tile_not_connectable(
    hass: HomeAssistant, mock_tile_ble_device: MagicMock
) -> None:
    """Test the Tile cannot be connected to when checking the key."""
    inject_bluetooth_service_info(hass, TILE_SERVICE_INFO)
    result = await _log_in(hass)

    with patch(
        "homeassistant.components.tile_ble.config_flow.async_ble_device_from_address",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ADDRESS: TILE_ADDRESS}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    mock_tile_ble_device.assert_not_called()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: TILE_ADDRESS}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    "service_infos",
    [
        pytest.param([], id="nothing_seen"),
        pytest.param([NOT_TILE_SERVICE_INFO], id="no_tiles_seen"),
    ],
)
@pytest.mark.usefixtures("mock_pytile")
async def test_no_devices(
    hass: HomeAssistant, service_infos: list[BluetoothServiceInfo]
) -> None:
    """Test the flow aborts when no Tiles are seen."""
    for service_info in service_infos:
        inject_bluetooth_service_info(hass, service_info)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ACCOUNT_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


@pytest.mark.usefixtures("mock_pytile")
async def test_configured_tiles_skipped(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test Tiles that are already set up are not offered again."""
    mock_config_entry.add_to_hass(hass)
    inject_bluetooth_service_info(hass, TILE_SERVICE_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ACCOUNT_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


@pytest.mark.usefixtures("mock_pytile")
async def test_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a Tile set up while the form was open is not added twice."""
    inject_bluetooth_service_info(hass, TILE_SERVICE_INFO)
    result = await _log_in(hass)

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: TILE_ADDRESS}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
