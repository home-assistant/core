"""Tests for syncthru config flow."""

import re

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components import ssdp
from homeassistant.components.syncthru.config_flow import SyncThru
from homeassistant.components.syncthru.const import DOMAIN
from homeassistant.const import CONF_NAME, CONF_URL

from tests.async_mock import patch
from tests.common import MockConfigEntry, mock_coro

FIXTURE_USER_INPUT = {
    CONF_URL: "http://192.168.1.2/",
    CONF_NAME: "My Printer",
}


def mock_connection(aioclient_mock):
    """Mock syncthru connection."""
    aioclient_mock.get(
        re.compile("."),
        text="""
{
\tstatus: {
\thrDeviceStatus: 2,
\tstatus1: "  Sleeping...   "
\t},
\tidentity: {
\tserial_num: "000000000000000",
\t}
}
        """,
    )


async def test_show_setup_form(hass):
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=None
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_already_configured_by_url(hass, aioclient_mock):
    """Test we match and update already configured devices by URL."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    udn = "uuid:XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"
    MockConfigEntry(
        domain=DOMAIN,
        data={**FIXTURE_USER_INPUT, CONF_NAME: "Already configured"},
        title="Already configured",
        unique_id=udn,
    ).add_to_hass(hass)
    mock_connection(aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=FIXTURE_USER_INPUT,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_URL] == FIXTURE_USER_INPUT[CONF_URL]
    assert result["data"][CONF_NAME] == FIXTURE_USER_INPUT[CONF_NAME]
    assert result["result"].unique_id == udn


async def test_syncthru_not_supported(hass):
    """Test we show user form on unsupported device."""
    with patch.object(SyncThru, "update", side_effect=ValueError):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=FIXTURE_USER_INPUT,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_URL: "syncthru_not_supported"}


async def test_unknown_state(hass):
    """Test we show user form on unsupported device."""
    with patch.object(SyncThru, "update", return_value=mock_coro()), patch.object(
        SyncThru, "is_unknown_state", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=FIXTURE_USER_INPUT,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_URL: "unknown_state"}


async def test_success(hass, aioclient_mock):
    """Test successful flow provides entry creation data."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    mock_connection(aioclient_mock)

    with patch(
        "homeassistant.components.syncthru.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=FIXTURE_USER_INPUT,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_URL] == FIXTURE_USER_INPUT[CONF_URL]
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_ssdp(hass, aioclient_mock):
    """Test SSDP discovery initiates config properly."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    mock_connection(aioclient_mock)

    url = "http://192.168.1.2/"
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data={
            ssdp.ATTR_SSDP_LOCATION: "http://192.168.1.2:5200/Printer.xml",
            ssdp.ATTR_UPNP_DEVICE_TYPE: "urn:schemas-upnp-org:device:Printer:1",
            ssdp.ATTR_UPNP_MANUFACTURER: "Samsung Electronics",
            ssdp.ATTR_UPNP_PRESENTATION_URL: url,
            ssdp.ATTR_UPNP_SERIAL: "00000000",
            ssdp.ATTR_UPNP_UDN: "uuid:XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "confirm"
    assert CONF_URL in result["data_schema"].schema
    for k in result["data_schema"].schema:
        if k == CONF_URL:
            assert k.default() == url
