"""Test helper vars and functions for InCharge component tests."""

from http import HTTPStatus
import json

import requests_mock

from homeassistant.components.incharge.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import JWT_TOKEN

from tests.common import MockConfigEntry

test_response_stations = json.loads(
    json.dumps(
        {
            "stations": [
                {
                    "name": "station1",
                },
                {
                    "name": "station2",
                },
            ]
        }
    )
)

test_response_station_data = json.loads(json.dumps([{"total": 1000.00}]))

authorisation_response = json.loads(json.dumps({"Authorization": JWT_TOKEN}))

authorisation_response_auth_endpoint_unauthorised = json.loads(
    json.dumps(
        {
            "timestamp": "2023-02-20T09:41:55",
            "message": "Login failed - incorrect username, password or configuration",
        }
    )
)

authorisation_response_endpoints_unauthorised = json.loads(
    json.dumps(
        {
            "timestamp": "2023-02-20T09:40:21.006+00:00",
            "status": 401,
            "error": "Unauthorized",
            "path": "/pub/consumption/",
        }
    )
)

entry = MockConfigEntry(
    domain=DOMAIN,
    data={CONF_USERNAME: "test_username", CONF_PASSWORD: "test_password"},
    entry_id="test_entry",
)


async def setup_integration(hass: HomeAssistant) -> None:
    """Set up an integration."""
    with requests_mock.Mocker() as mock_request:
        ## Sign-in
        mock_request.post(
            "https://businessspecificapimanglobal.azure-api.net/old-authorization/incharge-api/user/token",
            headers=authorisation_response,
            status_code=HTTPStatus.OK,
        )
        # Get stations
        mock_request.get(
            "https://businessspecificapimanglobal.azure-api.net/station-configuration/pub/stations",
            json=test_response_stations,
            status_code=HTTPStatus.OK,
        )
        mock_request.get(
            "https://businessspecificapimanglobal.azure-api.net/energy-consumptions/pub/consumption/station1?since=2000-01-01T00%3A00%3A00.00Z",
            json=test_response_station_data,
            status_code=HTTPStatus.OK,
        )
        mock_request.get(
            "https://businessspecificapimanglobal.azure-api.net/energy-consumptions/pub/consumption/station2?since=2000-01-01T00%3A00%3A00.00Z",
            json=test_response_station_data,
            status_code=HTTPStatus.OK,
        )

        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def setup_integration_connection_error(hass: HomeAssistant) -> None:
    """Generate a failed integration."""
    with requests_mock.Mocker() as mock_request:
        ## Sign-in
        mock_request.post(
            "https://businessspecificapimanglobal.azure-api.net/old-authorization/incharge-api/user/token",
            headers=authorisation_response_auth_endpoint_unauthorised,
            status_code=HTTPStatus.FORBIDDEN,
        )
        # Get stations
        mock_request.get(
            "https://businessspecificapimanglobal.azure-api.net/station-configuration/pub/stations",
            json=authorisation_response_endpoints_unauthorised,
            status_code=HTTPStatus.FORBIDDEN,
        )
        mock_request.get(
            "https://businessspecificapimanglobal.azure-api.net/energy-consumptions/pub/consumption/station1?since=2000-01-01T00%3A00%3A00.00Z",
            json=authorisation_response_endpoints_unauthorised,
            status_code=HTTPStatus.FORBIDDEN,
        )
        mock_request.get(
            "https://businessspecificapimanglobal.azure-api.net/energy-consumptions/pub/consumption/station2?since=2000-01-01T00%3A00%3A00.00Z",
            json=authorisation_response_endpoints_unauthorised,
            status_code=HTTPStatus.FORBIDDEN,
        )

        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
