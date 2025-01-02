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


@patch("homeassistant.components.eheimdigital.config_flow.asyncio.Event", new=AsyncMock)
async def test_full_flow(hass: HomeAssistant, eheimdigital_hub_mock: AsyncMock) -> None:
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
    assert (
        result["result"].unique_id
        == eheimdigital_hub_mock.return_value.main.mac_address
    )


@patch("homeassistant.components.eheimdigital.config_flow.asyncio.Event", new=AsyncMock)
@pytest.mark.parametrize(
    ("side_effect", "error_value"),
    [(ClientConnectionError(), "cannot_connect"), (Exception(), "unknown")],
)
async def test_flow_errors(
    hass: HomeAssistant,
    eheimdigital_hub_mock: AsyncMock,
    side_effect: BaseException,
    error_value: str,
) -> None:
    """Test flow errors."""
    eheimdigital_hub_mock.return_value.connect.side_effect = side_effect

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
    assert result["errors"] == {"base": error_value}

    eheimdigital_hub_mock.return_value.connect.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == USER_INPUT[CONF_HOST]
    assert result["data"] == USER_INPUT
    assert (
        result["result"].unique_id
        == eheimdigital_hub_mock.return_value.main.mac_address
    )


@patch("homeassistant.components.eheimdigital.config_flow.asyncio.Event", new=AsyncMock)
async def test_zeroconf_flow(
    hass: HomeAssistant, eheimdigital_hub_mock: AsyncMock
) -> None:
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
    assert (
        result["result"].unique_id
        == eheimdigital_hub_mock.return_value.main.mac_address
    )


@pytest.mark.parametrize(
    ("side_effect", "error_value"),
    [(ClientConnectionError(), "cannot_connect"), (Exception(), "unknown")],
)
@patch("homeassistant.components.eheimdigital.config_flow.asyncio.Event", new=AsyncMock)
async def test_zeroconf_flow_errors(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    side_effect: BaseException,
    error_value: str,
) -> None:
    """Test zeroconf flow errors."""
    eheimdigital_hub_mock.return_value.connect.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == error_value


@patch("homeassistant.components.eheimdigital.config_flow.asyncio.Event", new=AsyncMock)
async def test_abort(hass: HomeAssistant, eheimdigital_hub_mock: AsyncMock) -> None:
    """Test flow abort on matching data or unique_id."""
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
    assert (
        result["result"].unique_id
        == eheimdigital_hub_mock.return_value.main.mac_address
    )

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"

    result3 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        {CONF_HOST: "eheimdigital2"},
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
