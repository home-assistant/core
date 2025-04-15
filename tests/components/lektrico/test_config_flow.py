"""Tests for the Lektrico Charging Station config flow."""

import dataclasses
from ipaddress import ip_address

from lektricowifi import DeviceConnectionError

from homeassistant.components.lektrico.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import (
    ATTR_HW_VERSION,
    ATTR_SERIAL_NUMBER,
    CONF_HOST,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    MOCKED_DEVICE_BOARD_REV,
    MOCKED_DEVICE_IP_ADDRESS,
    MOCKED_DEVICE_SERIAL_NUMBER,
    MOCKED_DEVICE_TYPE,
    MOCKED_DEVICE_ZEROCONF_DATA,
)

from tests.common import MockConfigEntry


async def test_user_setup(hass: HomeAssistant, mock_device, mock_setup_entry) -> None:
    """Test manually setting up."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER
    assert "flow_id" in result

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCKED_DEVICE_IP_ADDRESS,
        },
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == f"{MOCKED_DEVICE_TYPE}_{MOCKED_DEVICE_SERIAL_NUMBER}"
    assert result.get("data") == {
        CONF_HOST: MOCKED_DEVICE_IP_ADDRESS,
        ATTR_SERIAL_NUMBER: MOCKED_DEVICE_SERIAL_NUMBER,
        CONF_TYPE: MOCKED_DEVICE_TYPE,
        ATTR_HW_VERSION: MOCKED_DEVICE_BOARD_REV,
    }
    assert "result" in result
    assert len(mock_setup_entry.mock_calls) == 1
    assert result.get("result").unique_id == MOCKED_DEVICE_SERIAL_NUMBER


async def test_user_setup_already_exists(
    hass: HomeAssistant, mock_device, mock_config_entry: MockConfigEntry
) -> None:
    """Test manually setting up when the device already exists."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCKED_DEVICE_IP_ADDRESS,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_setup_device_offline(hass: HomeAssistant, mock_device) -> None:
    """Test manually setting up when device is offline."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    mock_device.device_config.side_effect = DeviceConnectionError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCKED_DEVICE_IP_ADDRESS,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: "cannot_connect"}
    assert result["step_id"] == "user"

    mock_device.device_config.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCKED_DEVICE_IP_ADDRESS,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_discovered_zeroconf(
    hass: HomeAssistant, mock_device, mock_setup_entry
) -> None:
    """Test we can setup when discovered from zeroconf."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=MOCKED_DEVICE_ZEROCONF_DATA,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result.get("step_id") == "confirm"

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        CONF_HOST: MOCKED_DEVICE_IP_ADDRESS,
        ATTR_SERIAL_NUMBER: MOCKED_DEVICE_SERIAL_NUMBER,
        CONF_TYPE: MOCKED_DEVICE_TYPE,
        ATTR_HW_VERSION: MOCKED_DEVICE_BOARD_REV,
    }
    assert result2["title"] == f"{MOCKED_DEVICE_TYPE}_{MOCKED_DEVICE_SERIAL_NUMBER}"


async def test_zeroconf_setup_already_exists(
    hass: HomeAssistant, mock_device, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort zeroconf flow if device already configured."""
    mock_config_entry.add_to_hass(hass)
    zc_data_new_ip = dataclasses.replace(MOCKED_DEVICE_ZEROCONF_DATA)
    zc_data_new_ip.ip_address = ip_address(MOCKED_DEVICE_IP_ADDRESS)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zc_data_new_ip,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_discovered_zeroconf_device_connection_error(
    hass: HomeAssistant, mock_device
) -> None:
    """Test we can setup when discovered from zeroconf but device went offline."""

    mock_device.device_config.side_effect = DeviceConnectionError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=MOCKED_DEVICE_ZEROCONF_DATA,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
