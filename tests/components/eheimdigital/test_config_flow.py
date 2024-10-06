"""Tests the config flow of EHEIM Digital."""

from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientConnectionError
import pytest

from homeassistant.components.eheimdigital.const import DOMAIN
from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

ZEROCONF_DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address("192.0.2.1"),
    ip_addresses=[ip_address("192.0.2.1")],
    hostname="eheimdigital.local.",
    name="eheimdigital._http._tcp.local.",
    port=80,
    type="_http._tcp.local.",
    properties={},
)

USER_INPUT = {CONF_HOST: "eheimdigital"}


@pytest.mark.usefixtures("eheimdigital_hub_mock")
@patch("homeassistant.components.eheimdigital.config_flow.asyncio.Event", new=AsyncMock)
async def test_full_flow(hass: HomeAssistant) -> None:
    """Test full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == USER_INPUT[CONF_HOST]
    assert result["data"] == USER_INPUT


@patch("homeassistant.components.eheimdigital.config_flow.asyncio.Event", new=AsyncMock)
async def test_flow_errors(
    hass: HomeAssistant,
    eheimdigital_hub_mock: AsyncMock,
) -> None:
    """Test flow errors."""
    eheimdigital_hub_mock.return_value.connect.side_effect = ClientConnectionError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    eheimdigital_hub_mock.return_value.connect.side_effect = Exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    eheimdigital_hub_mock.return_value.connect.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == USER_INPUT[CONF_HOST]
    assert result["data"] == USER_INPUT


@pytest.mark.usefixtures("eheimdigital_hub_mock")
@patch("homeassistant.components.eheimdigital.config_flow.asyncio.Event", new=AsyncMock)
async def test_zeroconf_flow(hass: HomeAssistant) -> None:
    """Test zeroconf flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ZEROCONF_DISCOVERY.host
    assert result["data"] == {
        CONF_HOST: ZEROCONF_DISCOVERY.host,
    }


@pytest.mark.usefixtures("eheimdigital_hub_mock")
@patch("homeassistant.components.eheimdigital.config_flow.asyncio.Event", new=AsyncMock)
async def test_zeroconf_flow_errors(
    hass: HomeAssistant, eheimdigital_hub_mock: MagicMock
) -> None:
    """Test zeroconf flow errors."""
    eheimdigital_hub_mock.return_value.connect.side_effect = ClientConnectionError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"

    eheimdigital_hub_mock.return_value.connect.side_effect = Exception()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"
