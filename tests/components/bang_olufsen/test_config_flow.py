"""Test the bang_olufsen config_flow."""

from unittest.mock import AsyncMock, Mock

from aiohttp.client_exceptions import ClientConnectorError
from mozart_api.exceptions import ApiException
import pytest

from homeassistant.components.bang_olufsen.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import (
    TEST_DATA_CREATE_ENTRY,
    TEST_DATA_USER,
    TEST_DATA_USER_INVALID,
    TEST_DATA_ZEROCONF,
    TEST_DATA_ZEROCONF_IPV6,
    TEST_DATA_ZEROCONF_NOT_MOZART,
)

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_config_flow_timeout_error(
    hass: HomeAssistant, mock_mozart_client: AsyncMock
) -> None:
    """Test we handle timeout_error."""
    mock_mozart_client.get_beolink_self.side_effect = TimeoutError()

    result_user = await hass.config_entries.flow.async_init(
        handler=DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=TEST_DATA_USER,
    )
    assert result_user["type"] is FlowResultType.FORM
    assert result_user["errors"] == {"base": "timeout_error"}

    assert mock_mozart_client.get_beolink_self.call_count == 1


async def test_config_flow_client_connector_error(
    hass: HomeAssistant, mock_mozart_client: AsyncMock
) -> None:
    """Test we handle client_connector_error."""
    mock_mozart_client.get_beolink_self.side_effect = ClientConnectorError(
        Mock(), Mock()
    )

    result_user = await hass.config_entries.flow.async_init(
        handler=DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=TEST_DATA_USER,
    )
    assert result_user["type"] is FlowResultType.FORM
    assert result_user["errors"] == {"base": "client_connector_error"}

    assert mock_mozart_client.get_beolink_self.call_count == 1


async def test_config_flow_invalid_ip(hass: HomeAssistant) -> None:
    """Test we handle invalid_ip."""

    result_user = await hass.config_entries.flow.async_init(
        handler=DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=TEST_DATA_USER_INVALID,
    )
    assert result_user["type"] is FlowResultType.FORM
    assert result_user["errors"] == {"base": "invalid_ip"}


async def test_config_flow_api_exception(
    hass: HomeAssistant, mock_mozart_client: AsyncMock
) -> None:
    """Test we handle api_exception."""
    mock_mozart_client.get_beolink_self.side_effect = ApiException()

    result_user = await hass.config_entries.flow.async_init(
        handler=DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=TEST_DATA_USER,
    )
    assert result_user["type"] is FlowResultType.FORM
    assert result_user["errors"] == {"base": "api_exception"}

    assert mock_mozart_client.get_beolink_self.call_count == 1


async def test_config_flow(hass: HomeAssistant, mock_mozart_client: AsyncMock) -> None:
    """Test config flow."""

    result_init = await hass.config_entries.flow.async_init(
        handler=DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=None,
    )

    assert result_init["type"] is FlowResultType.FORM
    assert result_init["step_id"] == "user"

    result_user = await hass.config_entries.flow.async_configure(
        flow_id=result_init["flow_id"],
        user_input=TEST_DATA_USER,
    )

    assert result_user["type"] is FlowResultType.CREATE_ENTRY
    assert result_user["data"] == TEST_DATA_CREATE_ENTRY

    assert mock_mozart_client.get_beolink_self.call_count == 1


async def test_config_flow_zeroconf(
    hass: HomeAssistant, mock_mozart_client: AsyncMock
) -> None:
    """Test zeroconf discovery."""

    result_zeroconf = await hass.config_entries.flow.async_init(
        handler=DOMAIN,
        context={CONF_SOURCE: SOURCE_ZEROCONF},
        data=TEST_DATA_ZEROCONF,
    )

    assert result_zeroconf["type"] is FlowResultType.FORM
    assert result_zeroconf["step_id"] == "zeroconf_confirm"

    result_confirm = await hass.config_entries.flow.async_configure(
        flow_id=result_zeroconf["flow_id"],
        user_input=TEST_DATA_USER,
    )

    assert result_confirm["type"] is FlowResultType.CREATE_ENTRY
    assert result_confirm["data"] == TEST_DATA_CREATE_ENTRY

    assert mock_mozart_client.get_beolink_self.call_count == 1


async def test_config_flow_zeroconf_not_mozart_device(hass: HomeAssistant) -> None:
    """Test zeroconf discovery of invalid device."""

    result_user = await hass.config_entries.flow.async_init(
        handler=DOMAIN,
        context={CONF_SOURCE: SOURCE_ZEROCONF},
        data=TEST_DATA_ZEROCONF_NOT_MOZART,
    )

    assert result_user["type"] is FlowResultType.ABORT
    assert result_user["reason"] == "not_mozart_device"


async def test_config_flow_zeroconf_ipv6(hass: HomeAssistant) -> None:
    """Test zeroconf discovery with IPv6 IP address."""

    result_user = await hass.config_entries.flow.async_init(
        handler=DOMAIN,
        context={CONF_SOURCE: SOURCE_ZEROCONF},
        data=TEST_DATA_ZEROCONF_IPV6,
    )

    assert result_user["type"] is FlowResultType.ABORT
    assert result_user["reason"] == "ipv6_address"


async def test_config_flow_zeroconf_invalid_ip(
    hass: HomeAssistant, mock_mozart_client: AsyncMock
) -> None:
    """Test zeroconf discovery with invalid IP address."""
    mock_mozart_client.get_beolink_self.side_effect = ClientConnectorError(
        Mock(), Mock()
    )

    result_user = await hass.config_entries.flow.async_init(
        handler=DOMAIN,
        context={CONF_SOURCE: SOURCE_ZEROCONF},
        data=TEST_DATA_ZEROCONF,
    )

    assert result_user["type"] is FlowResultType.ABORT
    assert result_user["reason"] == "invalid_address"
