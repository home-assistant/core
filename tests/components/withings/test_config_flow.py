"""Tests for the Withings config flow."""
from aiohttp.web_request import BaseRequest
from asynctest import CoroutineMock, MagicMock
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.withings import const
from homeassistant.components.withings.config_flow import (
    register_flow_implementation,
    WithingsFlowHandler,
    WithingsAuthCallbackView,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType


@pytest.fixture(name="flow_handler")
def flow_handler_fixture(hass: HomeAssistantType):
    """Provide flow handler."""
    flow_handler = WithingsFlowHandler()
    flow_handler.hass = hass
    return flow_handler


def test_flow_handler_init(flow_handler: WithingsFlowHandler):
    """Test the init of the flow handler."""
    assert not flow_handler.flow_profile


def test_flow_handler_async_profile_config_entry(
    hass: HomeAssistantType, flow_handler: WithingsFlowHandler
):
    """Test profile config entry."""
    config_entries = [
        ConfigEntry(
            version=1,
            domain=const.DOMAIN,
            title="AAA",
            data={},
            source="source",
            connection_class="connection_class",
            system_options={},
        ),
        ConfigEntry(
            version=1,
            domain=const.DOMAIN,
            title="Person 1",
            data={const.PROFILE: "Person 1"},
            source="source",
            connection_class="connection_class",
            system_options={},
        ),
        ConfigEntry(
            version=1,
            domain=const.DOMAIN,
            title="BBB",
            data={},
            source="source",
            connection_class="connection_class",
            system_options={},
        ),
    ]

    hass.config_entries.async_entries = MagicMock(return_value=config_entries)

    config_entry = flow_handler.async_profile_config_entry

    assert not config_entry("GGGG")
    hass.config_entries.async_entries.assert_called_with(const.DOMAIN)

    assert not config_entry("CCC")
    hass.config_entries.async_entries.assert_called_with(const.DOMAIN)

    assert config_entry("Person 1") == config_entries[1]
    hass.config_entries.async_entries.assert_called_with(const.DOMAIN)


def test_flow_handler_get_auth_client(
    hass: HomeAssistantType, flow_handler: WithingsFlowHandler
):
    """Test creation of an auth client."""
    register_flow_implementation(
        hass, "my_client_id", "my_client_secret", "http://localhost/", ["Person 1"]
    )

    client = flow_handler.get_auth_client("Person 1")
    assert client.client_id == "my_client_id"
    assert client.consumer_secret == "my_client_secret"
    assert client.callback_uri.startswith(
        "http://localhost/api/withings/authorize?flow_id="
    )
    assert client.callback_uri.endswith("&profile=Person 1")
    assert client.scope == "user.info,user.metrics,user.activity"


async def test_auth_callback_view_get(hass: HomeAssistantType):
    """Test get api path."""
    view = WithingsAuthCallbackView()
    hass.config_entries.flow.async_configure = CoroutineMock(return_value="AAAA")

    request = MagicMock(spec=BaseRequest)
    request.app = {"hass": hass}

    # No args
    request.query = {}
    response = await view.get(request)
    assert response.status == 400
    hass.config_entries.flow.async_configure.assert_not_called()
    hass.config_entries.flow.async_configure.reset_mock()

    # Checking flow_id
    request.query = {"flow_id": "my_flow_id"}
    response = await view.get(request)
    assert response.status == 400
    hass.config_entries.flow.async_configure.assert_not_called()
    hass.config_entries.flow.async_configure.reset_mock()

    # Checking flow_id and profile
    request.query = {"flow_id": "my_flow_id", "profile": "my_profile"}
    response = await view.get(request)
    assert response.status == 400
    hass.config_entries.flow.async_configure.assert_not_called()
    hass.config_entries.flow.async_configure.reset_mock()

    # Checking flow_id, profile, code
    request.query = {
        "flow_id": "my_flow_id",
        "profile": "my_profile",
        "code": "my_code",
    }
    response = await view.get(request)
    assert response.status == 200
    hass.config_entries.flow.async_configure.assert_called_with(
        "my_flow_id", {const.PROFILE: "my_profile", const.CODE: "my_code"}
    )
    hass.config_entries.flow.async_configure.reset_mock()

    # Exception thrown
    hass.config_entries.flow.async_configure = CoroutineMock(
        side_effect=data_entry_flow.UnknownFlow()
    )
    request.query = {
        "flow_id": "my_flow_id",
        "profile": "my_profile",
        "code": "my_code",
    }
    response = await view.get(request)
    assert response.status == 400
    hass.config_entries.flow.async_configure.assert_called_with(
        "my_flow_id", {const.PROFILE: "my_profile", const.CODE: "my_code"}
    )
    hass.config_entries.flow.async_configure.reset_mock()


async def test_init_without_config(hass):
    """Try initializin a configg flow without it being configured."""
    result = await hass.config_entries.flow.async_init(
        "withings", context={"source": "user"}
    )

    assert result["type"] == "abort"
    assert result["reason"] == "no_flows"
