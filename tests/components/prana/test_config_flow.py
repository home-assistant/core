"""Tests for the Prana config flow."""

from prana_local_api_client.exceptions import (
    PranaApiCommunicationError as PranaCommunicationError,
)
import pytest

from homeassistant.components.prana.config_flow import SERVICE_TYPE
from homeassistant.components.prana.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo


@pytest.mark.asyncio
async def test_zeroconf_new_device_and_confirm(
    hass: HomeAssistant, mock_prana_api
) -> None:
    """Zeroconf discovery shows confirm form and creates a config entry."""
    info = ZeroconfServiceInfo(
        ip_address="192.168.1.30",
        ip_addresses=["192.168.1.30"],
        hostname="prana.local",
        name="TestNew._prana._tcp.local.",
        type=SERVICE_TYPE,
        port=1234,
        properties={},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "zeroconf"}, data=info
    )

    device_info = await mock_prana_api.get_device_info()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == device_info.label
    assert result2["result"].unique_id == device_info.manufactureId


@pytest.mark.asyncio
async def test_user_flow_with_manual_entry(hass: HomeAssistant, mock_prana_api) -> None:
    """User flow accepts manual host and creates entry after confirmation."""
    result_user = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result_user["type"] == FlowResultType.FORM
    assert result_user["step_id"] == "user"

    device_info = await mock_prana_api.get_device_info()

    result_after_submit = await hass.config_entries.flow.async_configure(
        result_user["flow_id"], user_input={CONF_HOST: "192.168.1.40"}
    )
    assert result_after_submit["type"] == FlowResultType.FORM
    assert result_after_submit["step_id"] == "confirm"

    result_create = await hass.config_entries.flow.async_configure(
        result_after_submit["flow_id"], user_input={}
    )
    assert result_create["type"] == FlowResultType.CREATE_ENTRY
    assert result_create["title"] == device_info.label
    assert result_create["result"].unique_id == device_info.manufactureId


@pytest.mark.asyncio
async def test_confirm_abort_no_devices(hass: HomeAssistant) -> None:
    """Confirm should not proceed when no discovery data exists."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=None
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "user"


@pytest.mark.asyncio
async def test_communication_error_on_device_info(
    hass: HomeAssistant, mock_prana_api
) -> None:
    """Communication errors when fetching device info surface as form errors."""
    mock_prana_api.get_device_info.side_effect = PranaCommunicationError(
        "Network error"
    )
    result_user = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result_user["type"] == FlowResultType.FORM
    assert result_user["step_id"] == "user"

    result_after_submit = await hass.config_entries.flow.async_configure(
        result_user["flow_id"], user_input={CONF_HOST: "192.168.1.50"}
    )
    assert result_after_submit["type"] == FlowResultType.FORM
    assert result_after_submit["step_id"] == "user"
    assert "invalid_device_or_unreachable" in result_after_submit["errors"].values()


async def test_configure_two_entries_same_device(
    hass: HomeAssistant, mock_prana_api
) -> None:
    """Second configuration for the same device should be aborted."""
    await test_user_flow_with_manual_entry(hass, mock_prana_api)

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result2_submit = await hass.config_entries.flow.async_configure(
        result2["flow_id"], user_input={CONF_HOST: "192.168.1.40"}
    )
    assert result2_submit["type"] == FlowResultType.ABORT
    assert result2_submit["reason"] == "already_configured"
