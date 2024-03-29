"""Tests for the Lektrico Charging Station config flow."""
import dataclasses
from ipaddress import ip_address
from unittest.mock import patch

from lektricowifi import DeviceConnectionError

from homeassistant import config_entries
from homeassistant.components.lektrico.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_FRIENDLY_NAME, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    MOCKED_DEVICE_BAD_ID_ZEROCONF_DATA,
    MOCKED_DEVICE_BAD_NO_ID_ZEROCONF_DATA,
    MOCKED_DEVICE_FRIENDLY_NAME,
    MOCKED_DEVICE_IP_ADDRESS,
    MOCKED_DEVICE_SERIAL_NUMBER,
    MOCKED_DEVICE_TYPE,
    MOCKED_DEVICE_ZEROCONF_DATA,
    _patch_device_config,
)

from tests.common import MockConfigEntry


async def test_user_setup(hass: HomeAssistant) -> None:
    """Test manually setting up."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER
    assert "flow_id" in result

    with _patch_device_config(), patch(
        "homeassistant.components.lektrico.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: MOCKED_DEVICE_IP_ADDRESS,
                CONF_FRIENDLY_NAME: MOCKED_DEVICE_FRIENDLY_NAME,
            },
        )
        await hass.async_block_till_done()

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert (
        result.get("title")
        == f"{MOCKED_DEVICE_FRIENDLY_NAME}_{MOCKED_DEVICE_SERIAL_NUMBER}"
    )
    assert result.get("data") == {
        CONF_HOST: MOCKED_DEVICE_IP_ADDRESS,
        CONF_FRIENDLY_NAME: MOCKED_DEVICE_FRIENDLY_NAME,
    }
    assert "result" in result
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_setup_already_exists(hass: HomeAssistant) -> None:
    """Test manually setting up when the device already exists."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: MOCKED_DEVICE_IP_ADDRESS,
            CONF_FRIENDLY_NAME: MOCKED_DEVICE_FRIENDLY_NAME,
        },
        unique_id=MOCKED_DEVICE_SERIAL_NUMBER,
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_device_config():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: MOCKED_DEVICE_IP_ADDRESS,
                CONF_FRIENDLY_NAME: MOCKED_DEVICE_FRIENDLY_NAME,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_setup_device_offline(hass: HomeAssistant) -> None:
    """Test manually setting up when device is offline."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_device_config(exception=DeviceConnectionError):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: MOCKED_DEVICE_IP_ADDRESS,
                CONF_FRIENDLY_NAME: MOCKED_DEVICE_FRIENDLY_NAME,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert result["errors"] == {CONF_HOST: "cannot_connect"}


async def test_discovered_zeroconf(hass: HomeAssistant) -> None:
    """Test we can setup when discovered from zeroconf."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCKED_DEVICE_ZEROCONF_DATA,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        CONF_HOST: MOCKED_DEVICE_IP_ADDRESS,
        CONF_FRIENDLY_NAME: MOCKED_DEVICE_TYPE,
    }
    assert result2["title"] == f"{MOCKED_DEVICE_TYPE}_{MOCKED_DEVICE_SERIAL_NUMBER}"

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    zc_data_new_ip = dataclasses.replace(MOCKED_DEVICE_ZEROCONF_DATA)
    zc_data_new_ip.ip_address = ip_address(MOCKED_DEVICE_IP_ADDRESS)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zc_data_new_ip,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == MOCKED_DEVICE_IP_ADDRESS

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCKED_DEVICE_BAD_ID_ZEROCONF_DATA,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "missing_underline_in_id"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCKED_DEVICE_BAD_NO_ID_ZEROCONF_DATA,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "missing_id"
