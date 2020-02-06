"""Test the HVV Departures config flow."""
from asynctest import patch
from pygti.exceptions import CannotConnect, InvalidAuth

from homeassistant.components.hvv_departures import config_flow


async def test_user_flow(hass):
    """Test that config flow works."""
    flow = config_flow.ConfigFlow()
    flow.hass = hass

    with patch(
        "homeassistant.components.hvv_departures.config_flow.GTIHub.authenticate",
        return_value=True,
    ), patch(
        "pygti.gti.GTI.checkName",
        return_value={
            "returnCode": "OK",
            "results": [
                {
                    "name": "Wartenau",
                    "city": "Hamburg",
                    "combinedName": "Wartenau",
                    "id": "Master:10901",
                    "type": "STATION",
                    "coordinate": {"x": 10.035515, "y": 53.56478},
                    "serviceTypes": ["bus", "u"],
                    "hasStationInformation": True,
                }
            ],
        },
    ), patch(
        "pygti.gti.GTI.stationInformation",
        return_value={
            "returnCode": "OK",
            "partialStations": [
                {
                    "stationOutline": "http://www.geofox.de/images/mobi/stationDescriptions/U_Wartenau.ZM3.jpg",
                    "elevators": [
                        {
                            "label": "A",
                            "cabinWidth": 124,
                            "cabinLength": 147,
                            "doorWidth": 110,
                            "description": "Zugang Landwehr <-> Schalterhalle",
                            "elevatorType": "Durchlader",
                            "buttonType": "BRAILLE",
                            "state": "READY",
                        },
                        {
                            "lines": ["U1"],
                            "label": "B",
                            "cabinWidth": 123,
                            "cabinLength": 145,
                            "doorWidth": 90,
                            "description": "Schalterhalle <-> U1",
                            "elevatorType": "Durchlader",
                            "buttonType": "COMBI",
                            "state": "READY",
                        },
                    ],
                }
            ],
            "lastUpdate": {"date": "26.01.2020", "time": "22:49"},
        },
    ), patch(
        "homeassistant.components.hvv_departures.async_setup", return_value=True
    ), patch(
        "homeassistant.components.hvv_departures.async_setup_entry", return_value=True,
    ):

        # step: user

        result_user = await flow.async_step_user(
            user_input={
                "host": "api-test.geofox.de",
                "username": "test-username",
                "password": "test-password",
            }
        )

        assert result_user["step_id"] == "station"

        # step: station
        result_station = await flow.async_step_station(
            user_input={"station": "Wartenau"}
        )

        assert result_station["step_id"] == "station_select"

        # step: station_select
        result_station_select = await flow.async_step_station_select(
            user_input={"station": "Wartenau (STATION)"}
        )

        print(result_station_select)

        assert result_station_select["type"] == "create_entry"
        assert result_station_select["title"] == "Wartenau"
        assert result_station_select["data"] == {
            "host": "api-test.geofox.de",
            "username": "test-username",
            "password": "test-password",
            "station": {
                "name": "Wartenau",
                "city": "Hamburg",
                "combinedName": "Wartenau",
                "id": "Master:10901",
                "type": "STATION",
                "coordinate": {"x": 10.035515, "y": 53.56478},
                "serviceTypes": ["bus", "u"],
                "hasStationInformation": True,
            },
            "stationInformation": {
                "returnCode": "OK",
                "partialStations": [
                    {
                        "stationOutline": "http://www.geofox.de/images/mobi/stationDescriptions/U_Wartenau.ZM3.jpg",
                        "elevators": [
                            {
                                "label": "A",
                                "cabinWidth": 124,
                                "cabinLength": 147,
                                "doorWidth": 110,
                                "description": "Zugang Landwehr <-> Schalterhalle",
                                "elevatorType": "Durchlader",
                                "buttonType": "BRAILLE",
                                "state": "READY",
                            },
                            {
                                "lines": ["U1"],
                                "label": "B",
                                "cabinWidth": 123,
                                "cabinLength": 145,
                                "doorWidth": 90,
                                "description": "Schalterhalle <-> U1",
                                "elevatorType": "Durchlader",
                                "buttonType": "COMBI",
                                "state": "READY",
                            },
                        ],
                    }
                ],
                "lastUpdate": {"date": "26.01.2020", "time": "22:49"},
            },
        }


async def test_user_flow_no_results(hass):
    """Test that config flow works when there are no results."""
    flow = config_flow.ConfigFlow()
    flow.hass = hass

    with patch(
        "homeassistant.components.hvv_departures.config_flow.GTIHub.authenticate",
        return_value=True,
    ), patch(
        "pygti.gti.GTI.checkName", return_value={"returnCode": "OK", "results": []},
    ), patch(
        "homeassistant.components.hvv_departures.async_setup", return_value=True
    ), patch(
        "homeassistant.components.hvv_departures.async_setup_entry", return_value=True,
    ):

        # step: user

        result_user = await flow.async_step_user(
            user_input={
                "host": "api-test.geofox.de",
                "username": "test-username",
                "password": "test-password",
            }
        )

        assert result_user["step_id"] == "station"

        # step: station
        result_station = await flow.async_step_station(user_input={"station": " "})

        assert result_station["step_id"] == "station"
        assert result_station["errors"]["base"] == "no_results"


async def test_user_flow_invalid_auth(hass):
    """Test that config flow handles invalid auth."""
    flow = config_flow.ConfigFlow()
    flow.hass = hass

    with patch(
        "homeassistant.components.hvv_departures.config_flow.GTIHub.authenticate",
        side_effect=InvalidAuth(
            "ERROR_TEXT",
            "Bei der Verarbeitung der Anfrage ist ein technisches Problem aufgetreten.",
            "Authentication failed!",
        ),
    ):

        # step: user
        result_user = await flow.async_step_user(
            user_input={
                "host": "api-test.geofox.de",
                "username": "test-username",
                "password": "test-password",
            }
        )

        assert result_user["type"] == "form"
        assert result_user["errors"] == {"base": "invalid_auth"}


async def test_user_flow_cannot_connect(hass):
    """Test that config flow handles connection errors."""
    flow = config_flow.ConfigFlow()
    flow.hass = hass

    with patch(
        "homeassistant.components.hvv_departures.config_flow.GTIHub.authenticate",
        side_effect=CannotConnect(),
    ):

        # step: user
        result_user = await flow.async_step_user(
            user_input={
                "host": "api-test.geofox.de",
                "username": "test-username",
                "password": "test-password",
            }
        )

        assert result_user["type"] == "form"
        assert result_user["errors"] == {"base": "cannot_connect"}


async def test_user_flow_station(hass):
    """Test that config flow handles empty data on step station."""
    flow = config_flow.ConfigFlow()
    flow.hass = hass

    # step: station
    result_station = await flow.async_step_station(user_input=None)

    assert result_station["type"] == "form"
    assert result_station["step_id"] == "station"


async def test_user_flow_station_select(hass):
    """Test that config flow handles empty data on step station_select."""
    flow = config_flow.ConfigFlow()
    flow.hass = hass

    # step: station_select
    result_station_select = await flow.async_step_station_select(user_input=None)

    assert result_station_select["type"] == "form"
    assert result_station_select["step_id"] == "station_select"
