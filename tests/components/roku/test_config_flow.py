"""Test the Roku config flow."""
from socket import gaierror as SocketGIAError

from requests.exceptions import RequestException
from requests_mock import Mocker
from roku import RokuException

from homeassistant.components.roku.const import DOMAIN
from homeassistant.components.ssdp import (
    ATTR_SSDP_LOCATION,
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_SERIAL,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_SSDP, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_SOURCE
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.setup import async_setup_component

from tests.async_mock import patch
from tests.components.roku import (
    HOST,
    SSDP_LOCATION,
    UPNP_FRIENDLY_NAME,
    UPNP_SERIAL,
    mock_connection,
    setup_integration,
)


async def test_duplicate_error(hass: HomeAssistantType, requests_mock: Mocker) -> None:
    """Test that errors are shown when duplicates are added."""
    await setup_integration(hass, requests_mock, skip_entry_setup=True)

    mock_connection(requests_mock)

    user_input = {CONF_HOST: HOST}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_IMPORT}, data=user_input
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    user_input = {CONF_HOST: HOST}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data=user_input
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    discovery_info = {
        ATTR_UPNP_FRIENDLY_NAME: UPNP_FRIENDLY_NAME,
        ATTR_SSDP_LOCATION: SSDP_LOCATION,
        ATTR_UPNP_SERIAL: UPNP_SERIAL,
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_SSDP}, data=discovery_info
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_form(hass: HomeAssistantType, requests_mock: Mocker) -> None:
    """Test the user step."""
    await async_setup_component(hass, "persistent_notification", {})

    mock_connection(requests_mock)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    user_input = {CONF_HOST: HOST}
    with patch(
        "homeassistant.components.roku.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.roku.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"], user_input=user_input
        )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST

    assert result["data"]
    assert result["data"][CONF_HOST] == HOST

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistantType) -> None:
    """Test we handle cannot connect roku error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    with patch(
        "homeassistant.components.roku.config_flow.Roku._call",
        side_effect=RokuException,
    ) as mock_validate_input:
        result = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"], user_input={CONF_HOST: HOST}
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_connect"}

    await hass.async_block_till_done()
    assert len(mock_validate_input.mock_calls) == 1


async def test_form_cannot_connect_request(hass: HomeAssistantType) -> None:
    """Test we handle cannot connect request error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    user_input = {CONF_HOST: HOST}
    with patch(
        "homeassistant.components.roku.config_flow.Roku._call",
        side_effect=RequestException,
    ) as mock_validate_input:
        result = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"], user_input=user_input
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_connect"}

    await hass.async_block_till_done()
    assert len(mock_validate_input.mock_calls) == 1


async def test_form_cannot_connect_socket(hass: HomeAssistantType) -> None:
    """Test we handle cannot connect socket error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    user_input = {CONF_HOST: HOST}
    with patch(
        "homeassistant.components.roku.config_flow.Roku._call",
        side_effect=SocketGIAError,
    ) as mock_validate_input:
        result = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"], user_input=user_input
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_connect"}

    await hass.async_block_till_done()
    assert len(mock_validate_input.mock_calls) == 1


async def test_form_unknown_error(hass: HomeAssistantType) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    user_input = {CONF_HOST: HOST}
    with patch(
        "homeassistant.components.roku.config_flow.Roku._call", side_effect=Exception,
    ) as mock_validate_input:
        result = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"], user_input=user_input
        )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "unknown"

    await hass.async_block_till_done()
    assert len(mock_validate_input.mock_calls) == 1


async def test_import(hass: HomeAssistantType, requests_mock: Mocker) -> None:
    """Test the import step."""
    mock_connection(requests_mock)

    user_input = {CONF_HOST: HOST}
    with patch(
        "homeassistant.components.roku.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.roku.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_IMPORT}, data=user_input
        )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST

    assert result["data"]
    assert result["data"][CONF_HOST] == HOST

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_ssdp_discovery(hass: HomeAssistantType, requests_mock: Mocker) -> None:
    """Test the ssdp discovery step."""
    mock_connection(requests_mock)

    discovery_info = {
        ATTR_SSDP_LOCATION: SSDP_LOCATION,
        ATTR_UPNP_FRIENDLY_NAME: UPNP_FRIENDLY_NAME,
        ATTR_UPNP_SERIAL: UPNP_SERIAL,
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_SSDP}, data=discovery_info
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "ssdp_confirm"
    assert result["description_placeholders"] == {CONF_NAME: UPNP_FRIENDLY_NAME}

    with patch(
        "homeassistant.components.roku.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.roku.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"], user_input={}
        )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == UPNP_FRIENDLY_NAME

    assert result["data"]
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_NAME] == UPNP_FRIENDLY_NAME

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
