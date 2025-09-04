"""Test the Kuler Sky config flow."""

from unittest.mock import AsyncMock, Mock, patch

import pykulersky

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.kulersky.config_flow import DOMAIN
from homeassistant.config_entries import (
    SOURCE_BLUETOOTH,
    SOURCE_INTEGRATION_DISCOVERY,
    SOURCE_USER,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

KULERSKY_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="KulerLight",
    manufacturer_data={},
    service_data={},
    service_uuids=["8d96a001-0002-64c2-0001-9acc4838521c"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="KulerLight",
        manufacturer_data={},
        service_data={},
        service_uuids=["8d96a001-0002-64c2-0001-9acc4838521c"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "KulerLight"),
    time=0,
    connectable=True,
    tx_power=-127,
)


async def test_bluetooth_discovery(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth with a valid device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=KULERSKY_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch("pykulersky.Light", Mock(return_value=AsyncMock())):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: "AA:BB:CC:DD:EE:FF"},
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "KulerLight (EEFF)"
    assert result["data"] == {
        CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
    }


async def test_integration_discovery(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth with a valid device."""
    with patch(
        "homeassistant.components.kulersky.config_flow.async_last_service_info",
        return_value=KULERSKY_SERVICE_INFO,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_INTEGRATION_DISCOVERY},
            data={CONF_ADDRESS: "AA:BB:CC:DD:EE:FF"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "KulerLight (EEFF)"
    assert result["data"] == {
        CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
    }


async def test_integration_discovery_no_last_service_info(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth with a valid device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data={CONF_ADDRESS: "AA:BB:CC:DD:EE:FF"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "AA:BB:CC:DD:EE:FF"
    assert result["data"] == {
        CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
    }


async def test_user_setup(hass: HomeAssistant) -> None:
    """Test the user manually setting up the integration."""
    with patch(
        "homeassistant.components.kulersky.config_flow.async_discovered_service_info",
        return_value=[
            KULERSKY_SERVICE_INFO,
            KULERSKY_SERVICE_INFO,
        ],  # Pass twice to test duplicate logic
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch("pykulersky.Light", Mock(return_value=AsyncMock())):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: "AA:BB:CC:DD:EE:FF"},
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "KulerLight (EEFF)"
    assert result["data"] == {
        CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
    }


async def test_user_setup_no_devices(hass: HomeAssistant) -> None:
    """Test the user manually setting up the integration."""
    with patch(
        "homeassistant.components.kulersky.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_connection_error(hass: HomeAssistant) -> None:
    """Test a connection error trying to set up."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=KULERSKY_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch("pykulersky.Light", Mock(side_effect=pykulersky.PykulerskyException)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: "AA:BB:CC:DD:EE:FF"},
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_unexpected_error(hass: HomeAssistant) -> None:
    """Test an unexpected error trying to set up."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=KULERSKY_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch("pykulersky.Light", Mock(side_effect=Exception)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: "AA:BB:CC:DD:EE:FF"},
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"
