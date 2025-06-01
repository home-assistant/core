"""Tests for syncthru config flow."""

from unittest.mock import AsyncMock, patch

from pysyncthru import SyncThruAPINotSupported

from homeassistant import config_entries
from homeassistant.components.syncthru.const import DOMAIN
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


async def test_show_setup_form(hass: HomeAssistant, mock_syncthru: AsyncMock) -> None:
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=None
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


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
        context={"source": config_entries.SOURCE_USER},
        data=FIXTURE_USER_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_URL: "unknown_state"}


async def test_success(hass: HomeAssistant, mock_syncthru: AsyncMock) -> None:
    """Test successful flow provides entry creation data."""

    with patch(
        "homeassistant.components.syncthru.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=FIXTURE_USER_INPUT,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_URL] == FIXTURE_USER_INPUT[CONF_URL]
    assert len(mock_setup_entry.mock_calls) == 1


async def test_ssdp(hass: HomeAssistant, mock_syncthru: AsyncMock) -> None:
    """Test SSDP discovery initiates config properly."""

    url = "http://192.168.1.2/"
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
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
