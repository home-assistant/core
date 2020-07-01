"""Tests for syncthru config flow."""

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import ssdp
from homeassistant.components.syncthru.const import DOMAIN
from homeassistant.const import CONF_NAME, CONF_URL

from tests.async_mock import patch
from tests.common import MockConfigEntry, mock_coro

FIXTURE_USER_INPUT = {
    CONF_URL: "http://192.168.1.2/",
    CONF_NAME: "My Printer",
}


async def test_show_setup_form(hass):
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=None
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_already_configured(hass):
    """Test we reject already configured devices by URL."""
    MockConfigEntry(
        domain=DOMAIN, data=FIXTURE_USER_INPUT, title="Already configured"
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=FIXTURE_USER_INPUT,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_syncthru_not_supported(hass):
    """Test we show user form on unsupported device."""
    with patch("pysyncthru.SyncThru.update", side_effect=ValueError):
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
    with patch("pysyncthru.SyncThru.update", return_value=mock_coro()), patch(
        "pysyncthru.SyncThru.serial_number", return_value="00000000"
    ), patch("pysyncthru.SyncThru.is_unknown_state", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=FIXTURE_USER_INPUT,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_URL: "unknown_state"}


async def test_success(hass):
    """Test successful flow provides entry creation data."""
    with patch("pysyncthru.SyncThru.update", return_value=mock_coro()), patch(
        "pysyncthru.SyncThru.serial_number", return_value="00000000"
    ), patch("pysyncthru.SyncThru.is_unknown_state", return_value=False):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=FIXTURE_USER_INPUT,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_URL] == FIXTURE_USER_INPUT[CONF_URL]


async def test_ssdp(hass):
    """Test SSDP discovery initiates config properly."""
    url = "http://192.168.1.2/"
    context = {"source": config_entries.SOURCE_SSDP}
    with patch("pysyncthru.SyncThru.update", return_value=mock_coro()), patch(
        "pysyncthru.SyncThru.serial_number", return_value="00000000"
    ), patch("pysyncthru.SyncThru.is_unknown_state", return_value=False):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context=context,
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
