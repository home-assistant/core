"""Tests for the Withings config flow."""
from aiohttp.web_request import BaseRequest
from asynctest import CoroutineMock, MagicMock

from homeassistant import data_entry_flow
from homeassistant.components.withings import const
from homeassistant.components.withings.config_flow import WithingsAuthCallbackView
from homeassistant.helpers.typing import HomeAssistantType


async def test_auth_callback_view_get(hass: HomeAssistantType) -> None:
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


async def test_init_without_config(hass) -> None:
    """Try initializin a configg flow without it being configured."""
    result = await hass.config_entries.flow.async_init(
        "withings", context={"source": "user"}
    )

    assert result["type"] == "abort"
    assert result["reason"] == "no_flows"
