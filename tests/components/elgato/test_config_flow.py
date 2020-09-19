"""Tests for the Elgato Key Light config flow."""
import aiohttp

from homeassistant import data_entry_flow
from homeassistant.components.elgato import config_flow
from homeassistant.components.elgato.const import CONF_SERIAL_NUMBER
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from . import init_integration

from tests.common import load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_show_user_form(hass: HomeAssistant) -> None:
    """Test that the user set up form is served."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_show_zeroconf_confirm_form(hass: HomeAssistant) -> None:
    """Test that the zeroconf confirmation form is served."""
    flow = config_flow.ElgatoFlowHandler()
    flow.hass = hass
    flow.context = {"source": SOURCE_ZEROCONF, CONF_SERIAL_NUMBER: "12345"}
    result = await flow.async_step_zeroconf_confirm()

    assert result["description_placeholders"] == {CONF_SERIAL_NUMBER: "12345"}
    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_show_zerconf_form(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that the zeroconf confirmation form is served."""
    aioclient_mock.get(
        "http://1.2.3.4:9123/elgato/accessory-info",
        text=load_fixture("elgato/info.json"),
        headers={"Content-Type": "application/json"},
    )

    flow = config_flow.ElgatoFlowHandler()
    flow.hass = hass
    flow.context = {"source": SOURCE_ZEROCONF}
    result = await flow.async_step_zeroconf({"host": "1.2.3.4", "port": 9123})

    assert flow.context[CONF_HOST] == "1.2.3.4"
    assert flow.context[CONF_PORT] == 9123
    assert flow.context[CONF_SERIAL_NUMBER] == "CN11A1A00001"
    assert result["description_placeholders"] == {CONF_SERIAL_NUMBER: "CN11A1A00001"}
    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we show user form on Elgato Key Light connection error."""
    aioclient_mock.get("http://1.2.3.4/elgato/accessory-info", exc=aiohttp.ClientError)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "1.2.3.4", CONF_PORT: 9123},
    )

    assert result["errors"] == {"base": "connection_error"}
    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_zeroconf_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow on Elgato Key Light connection error."""
    aioclient_mock.get("http://1.2.3.4/elgato/accessory-info", exc=aiohttp.ClientError)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data={"host": "1.2.3.4", "port": 9123},
    )

    assert result["reason"] == "connection_error"
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_zeroconf_confirm_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow on Elgato Key Light connection error."""
    aioclient_mock.get("http://1.2.3.4/elgato/accessory-info", exc=aiohttp.ClientError)

    flow = config_flow.ElgatoFlowHandler()
    flow.hass = hass
    flow.context = {
        "source": SOURCE_ZEROCONF,
        CONF_HOST: "1.2.3.4",
        CONF_PORT: 9123,
    }
    result = await flow.async_step_zeroconf_confirm(
        user_input={CONF_HOST: "1.2.3.4", CONF_PORT: 9123}
    )

    assert result["reason"] == "connection_error"
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_zeroconf_no_data(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort if zeroconf provides no data."""
    flow = config_flow.ElgatoFlowHandler()
    flow.hass = hass
    result = await flow.async_step_zeroconf()

    assert result["reason"] == "connection_error"
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_user_device_exists_abort(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow if Elgato Key Light device already configured."""
    await init_integration(hass, aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "1.2.3.4", CONF_PORT: 9123},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_zeroconf_device_exists_abort(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort zeroconf flow if Elgato Key Light device already configured."""
    await init_integration(hass, aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data={"host": "1.2.3.4", "port": 9123},
    )

    assert result["reason"] == "already_configured"
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_ZEROCONF, CONF_HOST: "1.2.3.4", "port": 9123},
        data={"host": "5.6.7.8", "port": 9123},
    )

    assert result["reason"] == "already_configured"
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT

    entries = hass.config_entries.async_entries(config_flow.DOMAIN)
    assert entries[0].data[CONF_HOST] == "5.6.7.8"


async def test_full_user_flow_implementation(
    hass: HomeAssistant, aioclient_mock
) -> None:
    """Test the full manual user flow from start to finish."""
    aioclient_mock.get(
        "http://1.2.3.4:9123/elgato/accessory-info",
        text=load_fixture("elgato/info.json"),
        headers={"Content-Type": "application/json"},
    )

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "1.2.3.4", CONF_PORT: 9123}
    )

    assert result["data"][CONF_HOST] == "1.2.3.4"
    assert result["data"][CONF_PORT] == 9123
    assert result["data"][CONF_SERIAL_NUMBER] == "CN11A1A00001"
    assert result["title"] == "CN11A1A00001"
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    entries = hass.config_entries.async_entries(config_flow.DOMAIN)
    assert entries[0].unique_id == "CN11A1A00001"


async def test_full_zeroconf_flow_implementation(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the full manual user flow from start to finish."""
    aioclient_mock.get(
        "http://1.2.3.4:9123/elgato/accessory-info",
        text=load_fixture("elgato/info.json"),
        headers={"Content-Type": "application/json"},
    )

    flow = config_flow.ElgatoFlowHandler()
    flow.hass = hass
    flow.context = {"source": SOURCE_ZEROCONF}
    result = await flow.async_step_zeroconf({"host": "1.2.3.4", "port": 9123})

    assert flow.context[CONF_HOST] == "1.2.3.4"
    assert flow.context[CONF_PORT] == 9123
    assert flow.context[CONF_SERIAL_NUMBER] == "CN11A1A00001"
    assert result["description_placeholders"] == {CONF_SERIAL_NUMBER: "CN11A1A00001"}
    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    result = await flow.async_step_zeroconf_confirm(user_input={CONF_HOST: "1.2.3.4"})
    assert result["data"][CONF_HOST] == "1.2.3.4"
    assert result["data"][CONF_PORT] == 9123
    assert result["data"][CONF_SERIAL_NUMBER] == "CN11A1A00001"
    assert result["title"] == "CN11A1A00001"
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
