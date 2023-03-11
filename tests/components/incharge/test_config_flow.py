"""Test the Wallbox config flow."""
from http import HTTPStatus
import json

import requests_mock

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.incharge.config_flow import InChargeConfigFlow
from homeassistant.components.incharge.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import authorisation_response_auth_endpoint_unauthorised, test_response_stations


async def test_show_set_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    flow = InChargeConfigFlow()
    flow.hass = hass
    result = await flow.async_step_user(user_input=None)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_form_cannot_authenticate(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with requests_mock.Mocker() as mock_request:
        mock_request.post(
            "https://businessspecificapimanglobal.azure-api.net/old-authorization/incharge-api/user/token",
            headers=json.loads(json.dumps({"Authorization": "Basic sdfsdfs"})),
            json=authorisation_response_auth_endpoint_unauthorised,
            status_code=HTTPStatus.UNAUTHORIZED,
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_forbidden(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error with forbidden status."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with requests_mock.Mocker() as mock_request:
        mock_request.post(
            "https://businessspecificapimanglobal.azure-api.net/old-authorization/incharge-api/user/token",
            headers=json.loads(json.dumps({"Authorization": "Basic sdfsdfs"})),
            json=authorisation_response_auth_endpoint_unauthorised,
            status_code=HTTPStatus.FORBIDDEN,
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with requests_mock.Mocker() as mock_request:
        mock_request.post(
            "https://businessspecificapimanglobal.azure-api.net/old-authorization/incharge-api/user/token",
            headers=json.loads(json.dumps({"Authorization": "Basic sdfsdfs"})),
            status_code=HTTPStatus.NOT_FOUND,
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_valid_input(hass: HomeAssistant) -> None:
    """Test we can validate input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with requests_mock.Mocker() as mock_request:
        mock_request.post(
            "https://businessspecificapimanglobal.azure-api.net/old-authorization/incharge-api/user/token",
            headers=json.loads(json.dumps({"Authorization": "Basic sdfsdfs"})),
            status_code=HTTPStatus.OK,
        )
        mock_request.get(
            "https://businessspecificapimanglobal.azure-api.net/station-configuration/pub/stations",
            json=test_response_stations,
            status_code=HTTPStatus.OK,
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["result"].state == config_entries.ConfigEntryState.LOADED
