"""Tests for syncthru config flow."""

from unittest.mock import AsyncMock

from pysyncthru import SyncThruAPINotSupported

from homeassistant import config_entries
from homeassistant.components.syncthru.const import DOMAIN
from homeassistant.config_entries import SOURCE_SSDP, SOURCE_USER
from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_DEVICE_TYPE,
    ATTR_UPNP_MANUFACTURER,
    ATTR_UPNP_PRESENTATION_URL,
    ATTR_UPNP_SERIAL,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)

from tests.common import MockConfigEntry

FIXTURE_USER_INPUT = {
    CONF_URL: "http://192.168.1.2/",
    CONF_NAME: "My Printer",
}


async def test_full_flow(
    hass: HomeAssistant, mock_syncthru: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test the full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=FIXTURE_USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == FIXTURE_USER_INPUT
    assert result["result"].unique_id is None


async def test_already_configured_by_url(
    hass: HomeAssistant, mock_syncthru: AsyncMock
) -> None:
    """Test we match and update already configured devices by URL."""

    udn = "uuid:XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"
    MockConfigEntry(
        domain=DOMAIN,
        data={**FIXTURE_USER_INPUT, CONF_NAME: "Already configured"},
        title="Already configured",
        unique_id=udn,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=FIXTURE_USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_URL] == FIXTURE_USER_INPUT[CONF_URL]
    assert result["data"][CONF_NAME] == FIXTURE_USER_INPUT[CONF_NAME]
    assert result["result"].unique_id == udn


async def test_syncthru_not_supported(
    hass: HomeAssistant, mock_syncthru: AsyncMock
) -> None:
    """Test we show user form on unsupported device."""
    mock_syncthru.update.side_effect = SyncThruAPINotSupported
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=FIXTURE_USER_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_URL: "syncthru_not_supported"}


async def test_unknown_state(hass: HomeAssistant, mock_syncthru: AsyncMock) -> None:
    """Test we show user form on unsupported device."""
    mock_syncthru.is_unknown_state.return_value = True
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=FIXTURE_USER_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_URL: "unknown_state"}

    mock_syncthru.is_unknown_state.return_value = False

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=FIXTURE_USER_INPUT,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_ssdp(
    hass: HomeAssistant, mock_syncthru: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test SSDP discovery initiates config properly."""

    url = "http://192.168.1.2/"
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location="http://192.168.1.2:5200/Printer.xml",
            upnp={
                ATTR_UPNP_DEVICE_TYPE: "urn:schemas-upnp-org:device:Printer:1",
                ATTR_UPNP_MANUFACTURER: "Samsung Electronics",
                ATTR_UPNP_PRESENTATION_URL: url,
                ATTR_UPNP_SERIAL: "00000000",
                ATTR_UPNP_UDN: "uuid:XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
            },
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert CONF_URL in result["data_schema"].schema
    for k in result["data_schema"].schema:
        if k == CONF_URL:
            assert k.default() == url

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_URL: url, CONF_NAME: "Printer"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_URL: url, CONF_NAME: "Printer"}
    assert result["result"].unique_id == "uuid:XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"


async def test_ssdp_already_configured(
    hass: HomeAssistant, mock_syncthru: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test SSDP discovery initiates config properly."""

    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, unique_id="uuid:XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"
    )

    url = "http://192.168.1.2/"
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location="http://192.168.1.2:5200/Printer.xml",
            upnp={
                ATTR_UPNP_DEVICE_TYPE: "urn:schemas-upnp-org:device:Printer:1",
                ATTR_UPNP_MANUFACTURER: "Samsung Electronics",
                ATTR_UPNP_PRESENTATION_URL: url,
                ATTR_UPNP_SERIAL: "00000000",
                ATTR_UPNP_UDN: "uuid:XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
            },
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
