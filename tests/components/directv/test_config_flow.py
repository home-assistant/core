"""Test the DirecTV config flow."""
from asynctest import patch

from homeassistant.components.directv.const import CONF_RECEIVER_ID, DOMAIN
from homeassistant.components.ssdp import ATTR_SSDP_LOCATION, ATTR_UPNP_SERIAL
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_SSDP, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_SOURCE
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.setup import async_setup_component

from tests.components.directv import (
    HOST,
    SSDP_LOCATION,
    UPNP_SERIAL,
    mock_connection,
    setup_integration,
)
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_duplicate_error(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that errors are shown when duplicates are added."""
    await setup_integration(hass, aioclient_mock)

    user_input = {CONF_HOST: HOST}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_IMPORT}, data=user_input,
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    user_input = {CONF_HOST: HOST}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data=user_input,
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    discovery_info = {ATTR_SSDP_LOCATION: SSDP_LOCATION, ATTR_UPNP_SERIAL: UPNP_SERIAL}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_SSDP}, data=discovery_info,
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_form(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we get the form."""
    mock_connection(aioclient_mock)
    await async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    user_input = {CONF_HOST: HOST}
    result = await hass.config_entries.flow.async_configure(
        flow_id=result["flow_id"], user_input=user_input,
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"]
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_RECEIVER_ID] == UPNP_SERIAL


async def test_form_cannot_connect(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we handle cannot connect error."""
    aioclient_mock.get(
        "http://127.0.0.1:8080/info/getVersion", status=500,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    user_input = {CONF_HOST: HOST}
    result = await hass.config_entries.flow.async_configure(
        flow_id=result["flow_id"], user_input=user_input,
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    user_input = {CONF_HOST: HOST}
    with patch(
        "homeassistant.components.directv.config_flow.DIRECTV.update",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"], user_input=user_input,
        )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "unknown"


async def test_import(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the import step."""
    mock_connection(aioclient_mock)

    user_input = {CONF_HOST: HOST}
    with patch(
        "homeassistant.components.directv.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.directv.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_IMPORT}, data=user_input,
        )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"]
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_RECEIVER_ID] == UPNP_SERIAL

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_ssdp_discovery(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the ssdp discovery step."""
    mock_connection(aioclient_mock)

    discovery_info = {ATTR_SSDP_LOCATION: SSDP_LOCATION, ATTR_UPNP_SERIAL: UPNP_SERIAL}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_SSDP}, data=discovery_info,
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "ssdp_confirm"
    assert result["description_placeholders"] == {CONF_NAME: HOST}

    user_input = {}
    with patch(
        "homeassistant.components.directv.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.directv.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"], user_input=user_input,
        )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"]
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_RECEIVER_ID] == UPNP_SERIAL

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_ssdp_discovery_confirm_abort(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we handle SSDP confirm cannot connect error."""
    aioclient_mock.get(
        "http://127.0.0.1:8080/info/getVersion", status=500,
    )

    discovery_info = {ATTR_SSDP_LOCATION: SSDP_LOCATION, ATTR_UPNP_SERIAL: UPNP_SERIAL}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_SSDP}, data=discovery_info,
    )

    discovery_info = {}
    result = await hass.config_entries.flow.async_configure(
        flow_id=result["flow_id"], user_input=discovery_info
    )

    assert result["type"] == RESULT_TYPE_ABORT


async def test_ssdp_discovery_confirm_unknown_error(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we handle SSDP confirm unknown error."""
    discovery_info = {ATTR_SSDP_LOCATION: SSDP_LOCATION, ATTR_UPNP_SERIAL: UPNP_SERIAL}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_SSDP}, data=discovery_info,
    )

    discovery_info = {}
    with patch(
        "homeassistant.components.directv.config_flow.DIRECTV.update",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"], user_input=discovery_info
        )

    assert result["type"] == RESULT_TYPE_ABORT
