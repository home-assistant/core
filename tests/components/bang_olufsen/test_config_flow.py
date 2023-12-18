"""Test the bang_olufsen config_flow."""


from unittest.mock import Mock

from aiohttp.client_exceptions import ClientConnectorError
import pytest

from homeassistant.components.bang_olufsen.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MockMozartClient
from .const import (
    TEST_DATA_CONFIRM,
    TEST_DATA_USER,
    TEST_DATA_USER_INVALID,
    TEST_DATA_ZEROCONF,
    TEST_DATA_ZEROCONF_NOT_MOZART,
)

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_config_flow_timeout_error(
    hass: HomeAssistant, mock_client: MockMozartClient
) -> None:
    """Test we handle timeout_error."""
    mock_client.get_beolink_self.side_effect = TimeoutError()

    result_user = await hass.config_entries.flow.async_init(
        handler=DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=TEST_DATA_USER,
    )
    assert result_user["type"] == FlowResultType.ABORT
    assert result_user["reason"] == "timeout_error"

    assert mock_client.get_beolink_self.call_count == 1


async def test_config_flow_client_connector_error(
    hass: HomeAssistant, mock_client: MockMozartClient
) -> None:
    """Test we handle client_connector_error."""
    mock_client.get_beolink_self.side_effect = ClientConnectorError(Mock(), Mock())

    result_user = await hass.config_entries.flow.async_init(
        handler=DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=TEST_DATA_USER,
    )
    assert result_user["type"] == FlowResultType.ABORT
    assert result_user["reason"] == "client_connector_error"

    assert mock_client.get_beolink_self.call_count == 1


async def test_config_flow_value_error(hass: HomeAssistant) -> None:
    """Test we handle value_error."""

    result_init = await hass.config_entries.flow.async_init(
        handler=DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=TEST_DATA_USER_INVALID,
    )
    assert result_init["type"] == FlowResultType.ABORT
    assert result_init["reason"] == "value_error"


async def test_config_flow(
    hass: HomeAssistant, mock_client: MockMozartClient, mock_setup_entry
) -> None:
    """Test config flow."""

    result_user = await hass.config_entries.flow.async_init(
        handler=DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=None,
    )

    assert result_user["type"] == FlowResultType.FORM
    assert result_user["step_id"] == "user"

    result_confirm = await hass.config_entries.flow.async_configure(
        flow_id=result_user["flow_id"],
        user_input=TEST_DATA_USER,
    )

    assert result_confirm["type"] == FlowResultType.FORM
    assert result_confirm["step_id"] == "confirm"

    result_entry = await hass.config_entries.flow.async_configure(
        flow_id=result_confirm["flow_id"],
        user_input=TEST_DATA_USER,
    )

    assert result_entry["type"] == FlowResultType.CREATE_ENTRY
    assert result_entry["data"] == TEST_DATA_CONFIRM

    assert mock_client.get_beolink_self.call_count == 1


async def test_config_flow_zeroconf(
    hass: HomeAssistant, mock_client: MockMozartClient, mock_setup_entry
) -> None:
    """Test zeroconf discovery."""

    result_zeroconf = await hass.config_entries.flow.async_init(
        handler=DOMAIN,
        context={CONF_SOURCE: SOURCE_ZEROCONF},
        data=TEST_DATA_ZEROCONF,
    )

    assert result_zeroconf["type"] == FlowResultType.FORM
    assert result_zeroconf["step_id"] == "confirm"

    result_confirm = await hass.config_entries.flow.async_configure(
        flow_id=result_zeroconf["flow_id"],
        user_input=TEST_DATA_USER,
    )

    assert result_confirm["type"] == FlowResultType.CREATE_ENTRY
    assert result_confirm["data"] == TEST_DATA_CONFIRM

    assert mock_client.get_beolink_self.call_count == 0


async def test_config_flow_zeroconf_not_mozart_device(hass: HomeAssistant) -> None:
    """Test zeroconf discovery of invalid device."""

    result_user = await hass.config_entries.flow.async_init(
        handler=DOMAIN,
        context={CONF_SOURCE: SOURCE_ZEROCONF},
        data=TEST_DATA_ZEROCONF_NOT_MOZART,
    )

    assert result_user["type"] == FlowResultType.ABORT
    assert result_user["reason"] == "not_mozart_device"
