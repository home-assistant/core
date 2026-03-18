"""Tests for the Prana config flow."""

from types import SimpleNamespace

from prana_local_api_client.exceptions import (
    PranaApiCommunicationError as PranaCommunicationError,
)

from homeassistant.components.prana.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import load_json_object_fixture

ZEROCONF_INFO = ZeroconfServiceInfo(
    ip_address="192.168.1.30",
    ip_addresses=["192.168.1.30"],
    hostname="prana.local",
    name="TestNew._prana._tcp.local.",
    type="_prana._tcp.local.",
    port=1234,
    properties={},
)


async def async_load_fixture(hass: HomeAssistant, filename: str) -> dict:
    """Load a fixture file."""
    return await hass.async_add_executor_job(load_json_object_fixture, filename, DOMAIN)


async def test_zeroconf_new_device_and_confirm(
    hass: HomeAssistant, mock_prana_api
) -> None:
    """Zeroconf discovery shows confirm form and creates a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_INFO
    )

    device_info = await async_load_fixture(hass, "device_info.json")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == device_info["label"]
    assert result["result"].unique_id == device_info["manufactureId"]
    assert result["result"].data == {CONF_HOST: "192.168.1.30"}


async def test_user_flow_with_manual_entry(hass: HomeAssistant, mock_prana_api) -> None:
    """User flow accepts manual host and creates entry after confirmation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    device_info = await async_load_fixture(hass, "device_info.json")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.40"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == device_info["label"]
    assert result["result"].unique_id == device_info["manufactureId"]
    assert result["result"].data == {CONF_HOST: "192.168.1.40"}


async def test_communication_error_on_device_info(
    hass: HomeAssistant, mock_prana_api
) -> None:
    """Communication errors when fetching device info surface as form errors."""

    # Setting an invalid device info, for abort the flow
    device_info_invalid = await async_load_fixture(hass, "device_info_invalid.json")
    mock_prana_api.get_device_info.return_value = SimpleNamespace(**device_info_invalid)
    mock_prana_api.get_device_info.side_effect = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.50"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_device"

    # Simulating a communication error
    device_info = await async_load_fixture(hass, "device_info.json")
    mock_prana_api.get_device_info.return_value = SimpleNamespace(**device_info)
    mock_prana_api.get_device_info.side_effect = PranaCommunicationError(
        "Network error"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.50"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "invalid_device_or_unreachable" in result["errors"].values()

    # Now simulating a successful fetch, without aborting
    mock_prana_api.get_device_info.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.50"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == device_info["label"]
    assert result["result"].unique_id == device_info["manufactureId"]
    assert result["result"].data == {CONF_HOST: "192.168.1.50"}


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_prana_api, mock_config_entry
) -> None:
    """Second configuration for the same device should be aborted."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.40"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_already_configured(
    hass: HomeAssistant, mock_prana_api, mock_config_entry
) -> None:
    """Zeroconf discovery of an already configured device should be aborted."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_INFO
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_invalid_device(hass: HomeAssistant, mock_prana_api) -> None:
    """Zeroconf discovery of an invalid device should be aborted."""
    mock_prana_api.get_device_info.side_effect = PranaCommunicationError(
        "Network error"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_INFO
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_device_or_unreachable"
