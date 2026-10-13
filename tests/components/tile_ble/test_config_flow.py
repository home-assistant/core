"""Tests for the Tile BLE config flow."""

import pytest

from homeassistant.components.tile_ble.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from . import (
    NEAR_TILE_SERVICE_INFO,
    NOT_TILE_SERVICE_INFO,
    TILE_ADDRESS,
    TILE_SERVICE_INFO,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow(hass: HomeAssistant) -> None:
    """Test picking a Tile, with the closest Tile listed first."""
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
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Tile"
    assert result["data"] == {}
    assert result["result"].unique_id == TILE_ADDRESS


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
